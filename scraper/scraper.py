

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
        log.warning(
            "Could not find a 'Company' header (got %s); defaulting to column 0",
            headers,
        )
        company_index = 0

    rows = table.find_elements(By.CSS_SELECTOR, "tbody tr")
    listings: list[JobListing] = []

    for row in rows:
        cells = row.find_elements(By.TAG_NAME, "td")
        if not cells or company_index >= len(cells):
            continue

        company = cells[company_index].text.strip()

        try:

            link = row.find_element(
                By.XPATH, ".//a[contains(., 'View') and contains(., 'Apply')]"
            )
            href = link.get_attribute("href")
        except NoSuchElementException:
            log.warning("Row for '%s' has no View & Apply link, skipping", company)
            continue

        if company and href:
            listings.append(JobListing(company=company, url=href))

    return listings



def get_known_urls(supabase: Client) -> set[str]:
    response = supabase.table("listings").select("url").execute()
    return {row["url"] for row in response.data}


def save_listing(supabase: Client, listing: JobListing) -> None:
    supabase.table("listings").insert(
        {"company": listing.company, "url": listing.url}
    ).execute()


def notify(listing: JobListing) -> None:
    response = requests.post(
        NOTIFY_URL,
        headers={"x-notifier-secret": NOTIFIER_SECRET_KEY},
        json={"company": listing.company, "url": listing.url},
        timeout=15,
    )
    if response.ok:
        log.info("Notified subscribers about '%s'", listing.company)
    else:
        log.error(
            "Notify request failed (%s): %s", response.status_code, response.text
        )


def main() -> int:
    supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    known_urls = get_known_urls(supabase)
    log.info("Loaded %d known listing URLs from Supabase", len(known_urls))

    driver = build_driver()
    try:
        login(driver)
        table = find_recent_jobs_table(driver)
        listings = parse_recent_jobs(table)
        log.info("Parsed %d rows from the RECENT JOBS table", len(listings))
    finally:
        driver.quit()

    new_count = 0
    for listing in listings:
        if listing.url in known_urls:
            continue

        log.info("New listing found: %s -> %s", listing.company, listing.url)
        save_listing(supabase, listing)
        known_urls.add(listing.url)
        notify(listing)
        new_count += 1

    log.info("Done. %d new listing(s) processed.", new_count)
    return 0


if __name__ == "__main__":
    start = time.time()
    try:
        exit_code = main()
    except Exception:
        log.exception("Scraper failed")
        exit_code = 1
    log.info("Finished in %.1fs", time.time() - start)
    sys.exit(exit_code)
