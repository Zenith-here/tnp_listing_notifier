## Device Setup & Notifications

To receive real-time placement alerts, open the link below and follow the instructions for your specific browser/device:

🔗 **Live Link:** [https://tnp-listing-notifier.vercel.app/](https://tnp-listing-notifier.vercel.app/)

---

### Android & Desktop (Chrome / Edge)

- Click the link above, tap **"Enable Notifications"**, and select **Allow** when prompted by the browser.

### Brave Browser Users

Brave aggressively blocks native web push hooks by default. If you prefer using Brave:

1. Open the Vercel link.
2. Click the **Brave Shield icon** in the address bar.
3. Toggle the shields **Down** for this site.
4. Click **"Enable Notifications"** again.

- _Alternative:_ Open the link inside **Google Chrome** instead.

### iOS / iPhone Users (Safari)

Apple restricts background web push notifications unless the site is added as a web app.

1. Open the Vercel link exclusively in **Safari** (Chrome/Brave on iOS will not work).
2. Tap the **Share** button (square icon with an up arrow) at the bottom of the screen.
3. Scroll down and select **"Add to Home Screen"**.
4. Close Safari, go to your iPhone's home screen, and open the new app icon.
5. Tap **"Enable Notifications"** inside the app and allow system permissions.

## Tech Stack & Architecture

This project is built using a modern serverless and automated architecture:

- **Web Scraper:** Python, Selenium (`undetected-chromedriver`)
- **Automation:** GitHub Actions (Cron Jobs)
- **Database:** Supabase (PostgreSQL)
- **Frontend & API:** Next.js (App Router), TypeScript
- **Hosting:** Vercel
- **Notifications:** Native Web Push API

---

## Contact & Connect

If you have any questions, suggestions, or want to discuss the architecture, feel free to reach out!

- **Email:** ash.alvin.1954@gmail.com
- **Twitter/X:** [@AshGupta_h3re](https://twitter.com/AshGupta_h3re)
