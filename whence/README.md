# Whence daily Maps leads

Runs on GitHub Actions every day at 06:13 IST. Nothing runs on your computer.

1. Picks the next 8 searches from `lead-queries.txt` (for example "skincare brand in Pune").
2. Runs Google Maps Scraper on them, collecting each business's website and email.
3. Keeps businesses with a website, a public email and 15 to 2,500 reviews, which leaves out tiny shops and big chains.
4. Skips anything already found, then saves today's leads to `leads/YYYY-MM-DD.csv` and adds them to `leads/all-leads.csv`.
5. If the Google Sheet secrets are set, it also adds the leads to a "Maps Leads" tab in your leads sheet.

## Run it now with your own searches

Go to **Actions > Whence daily Maps leads > Run workflow** and type searches separated by `;`.

## Change what it searches

Edit `lead-queries.txt`, with one search per line.

## Send leads to Google Sheets (optional)

Add these in **Settings > Secrets and variables > Actions**:

- `GOOGLE_SERVICE_ACCOUNT_JSON`: the JSON key of a Google Cloud service account. Share the sheet with that account's email as an Editor.
- `LEADS_SHEET_ID`: the long ID in the sheet's URL, the part between `/d/` and `/edit`.
