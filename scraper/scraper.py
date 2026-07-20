from __future__ import annotations
import traceback
import logging
import os
from dotenv import load_dotenv
load_dotenv("scraper/.env")
import sys
import time
from dataclasses import dataclass

import requests
import undetected_chromedriver as uc
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from supabase import Client, create_client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("tnp-scraper")

PORTAL_LOGIN_URL = os.environ["PORTAL_LOGIN_URL"]
PORTAL_JOBS_URL = os.environ.get("PORTAL_JOBS_URL") or PORTAL_LOGIN_URL
PORTAL_NEWS_URL = PORTAL_LOGIN_URL.rstrip('/') + "/newsevents"

PORTAL_USERNAME = os.environ["PORTAL_USERNAME"]
PORTAL_PASSWORD = os.environ["PORTAL_PASSWORD"]

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_ROLE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

NOTIFY_URL = os.environ["NOTIFY_URL"]  
NOTIFIER_SECRET_KEY = os.environ["NOTIFIER_SECRET_KEY"]

PAGE_LOAD_TIMEOUT = int(os.environ.get("PAGE_LOAD_TIMEOUT", "30"))


@dataclass
class JobListing:
    company: str
    url: str

@dataclass
class NewsEvent:
    title: str
    url: str


def build_driver() -> uc.Chrome:
    options = uc.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    driver = uc.Chrome(options=options, version_main=150)
    driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
    return driver


def login(driver: uc.Chrome) -> None:
    log.info("Navigating to login page: %s", PORTAL_LOGIN_URL)
    try:
        driver.set_window_size(1920, 1080)
        driver.get(PORTAL_LOGIN_URL)
        wait = WebDriverWait(driver, PAGE_LOAD_TIMEOUT)

        username_field = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='identity']"))
        )
        password_field = driver.find_element(By.CSS_SELECTOR, "input[name='password']")
        submit_button = driver.find_element(
            By.CSS_SELECTOR, "button[type='submit'], input[type='submit']"
        )

        username_field.clear()
        username_field.send_keys(PORTAL_USERNAME)
        password_field.clear()
        password_field.send_keys(PORTAL_PASSWORD)
        submit_button.click()

        wait.until(EC.url_changes(PORTAL_LOGIN_URL))
        log.info("Login submitted, current URL: %s", driver.current_url)
    except Exception as e:
        log.error("Login failed! Taking diagnostic screenshot...")
        driver.save_screenshot("error_screenshot.png")
        log.error("--- PAGE SOURCE START ---")
        log.error(driver.page_source[:5000]) 
        log.error("--- PAGE SOURCE END ---")
        raise e


def find_recent_jobs_table(driver: uc.Chrome):
    wait = WebDriverWait(driver, PAGE_LOAD_TIMEOUT)
    if driver.current_url != PORTAL_JOBS_URL:
        driver.get(PORTAL_JOBS_URL)

    table = wait.until(
        EC.presence_of_element_located(
            (
                By.XPATH,
                "//*[contains(translate(text(), "
                "'abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'), "
                "'RECENT JOBS')]/following::table[1]",
            )
        )
    )
    return table


def parse_recent_jobs(table) -> list[JobListing]:
    header_cells = table.find_elements(By.CSS_SELECTOR, "thead th")
    headers = [cell.text.strip().lower() for cell in header_cells]

    try:
        company_index = headers.index("company")
    except ValueError:
        log.warning("Could not find a 'Company' header (got %s); defaulting to column 0", headers)
        company_index = 0

    rows = table.find_elements(By.CSS_SELECTOR, "tbody tr")
    listings: list[JobListing] = []

    for row in rows:
        cells = row.find_elements(By.TAG_NAME, "td")
        if not cells or company_index >= len(cells):
            continue

        company = cells[company_index].text.strip()
        try:
            link = row.find_element(By.XPATH, ".//a[contains(., 'View') and contains(., 'Apply')]")
            href = link.get_attribute("href")
        except NoSuchElementException:
            log.warning("Row for '%s' has no View & Apply link, skipping", company)
            continue

        if company and href:
            listings.append(JobListing(company=company, url=href))
    return listings


def parse_news_events(driver: uc.Chrome) -> list[NewsEvent]:
    log.info("Navigating to News & Events page: %s", PORTAL_NEWS_URL)
    driver.get(PORTAL_NEWS_URL)
    wait = WebDriverWait(driver, PAGE_LOAD_TIMEOUT)
    
    table = wait.until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "table"))
    )
    
    rows = table.find_elements(By.CSS_SELECTOR, "tbody tr")
    events: list[NewsEvent] = []
    

    for row in rows[:10]:
        cells = row.find_elements(By.TAG_NAME, "td")
        if not cells:
            continue
        
        try:
            link_element = cells[0].find_element(By.TAG_NAME, "a")
            title = link_element.text.strip()
            href = link_element.get_attribute("href")
            
            if title and href:
                events.append(NewsEvent(title=title, url=href))
        except NoSuchElementException:
            continue
            
    return events


# Database Functions for Job Listings
def get_known_urls(supabase: Client) -> set[str]:
    response = supabase.table("listings").select("url").execute()
    return {row["url"] for row in response.data}

def save_listing(supabase: Client, listing: JobListing) -> None:
    supabase.table("listings").insert({"company": listing.company, "url": listing.url}).execute()

# Database Functions for News & Events
def get_known_news_urls(supabase: Client) -> set[str]:
    response = supabase.table("news_events").select("url").execute()
    return {row["url"] for row in response.data}

def save_news_event(supabase: Client, event: NewsEvent) -> None:
    supabase.table("news_events").insert({"title": event.title, "url": event.url}).execute()


def notify_subscriber(payload: dict) -> None:
    response = requests.post(
        NOTIFY_URL,
        headers={"x-notifier-secret": NOTIFIER_SECRET_KEY},
        json=payload,
        timeout=15,
    )
    if response.ok:
        log.info("Successfully fired webhook for: %s", payload.get("title") or payload.get("company"))
    else:
        log.error("Notify request failed (%s): %s", response.status_code, response.text)


def main() -> int:
    supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    
    # 1. Fetch historical keys
    known_job_urls = get_known_urls(supabase)
    known_news_urls = get_known_news_urls(supabase)
    log.info("Loaded %d jobs and %d news items from database storage.", len(known_job_urls), len(known_news_urls))

    driver = build_driver()
    listings = []
    events = []
    
    try:
        login(driver)
        
        # Scrape Part A: Job Listings
        job_table = find_recent_jobs_table(driver)
        listings = parse_recent_jobs(job_table)
        log.info("Parsed %d items from the RECENT JOBS table", len(listings))
        
        # Scrape Part B: News & Events
        events = parse_news_events(driver)
        log.info("Parsed %d items from the NEWS & EVENTS table", len(events))
        
    finally:
        driver.quit()

    # 2. Process Job Matches
    new_jobs_count = 0
    for listing in listings:
        if listing.url in known_job_urls:
            continue

        log.info("New job detected: %s", listing.company)
        save_listing(supabase, listing)
        known_job_urls.add(listing.url)
        
        notify_subscriber({
            "type": "job",
            "company": listing.company,
            "title": f"New TnP Job: {listing.company}",
            "url": listing.url
        })
        new_jobs_count += 1

   
    new_news_count = 0
    is_news_cold_start = len(known_news_urls) == 0
    
    for event in events:
        if event.url in known_news_urls:
            continue

        log.info("New portal notice detected: %s", event.title)
        save_news_event(supabase, event)
        known_news_urls.add(event.url)
        
        if not is_news_cold_start:
            notify_subscriber({
                "type": "news",
                "title": f"📢 Portal Update: {event.title}",
                "url": event.url
            })
        else:
            log.info("Cold start: Tracking '%s' without sending notification", event.title)
            
        new_news_count += 1

    log.info("Done. Processed %d new job(s) and %d new event updates.", new_jobs_count, new_news_count)
    return 0


if __name__ == "__main__":
    start = time.time()
    try:
        exit_code = main()
    except Exception:
        log.exception("Scraper execution halted due to unhandled error")
        exit_code = 1
    log.info("Finished execution cycle in %.1fs", time.time() - start)
    sys.exit(exit_code)