# Whence daily Maps leads

Runs on GitHub Actions every day at 06:13 IST and adds new leads to the **Maps Leads** tab of the Whence Lead Crawler sheet. Nothing runs on your computer.

1. Reads the searches from the sheet's **Maps Config** tab (rows marked Active), then adds 4 more from `lead-queries.txt` so it covers more of India.
2. Runs Google Maps Scraper on them and visits each business's website to find an email.
3. Keeps businesses that have a website and an email, are open, and meet the row's "Min reviews" setting.
4. Skips anyone already in Maps Leads, India, International or Coaches, matching by website, email, Place ID or name.
5. Adds the rest to Maps Leads with Status "New" and an empty Outreach stage, so your outreach picks them up. It also fills in "Last run" in Maps Config.

## Change what it searches

Edit the **Maps Config** tab in the sheet. "Max results" 20, 40 or 60 sets how deep it scrolls. Extra rotating searches live in `lead-queries.txt`.

## Run it now

**Actions > Whence daily Maps leads > Run workflow.** You can type one-off searches separated by `;`.

## Secrets it needs

In **Settings > Secrets and variables > Actions**:

- `GOOGLE_SERVICE_ACCOUNT_JSON`: the JSON key of a Google Cloud service account. Share the sheet with that account's email as an Editor.

The sheet ID is already set to the Whence Lead Crawler sheet. To use another sheet, add a `LEADS_SHEET_ID` secret.

Leads are never saved in this repo, because the repo is public. Each run's files are kept as a download on the run page for 14 days.
