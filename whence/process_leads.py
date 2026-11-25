"""Turn raw scraper output into Whence leads.

Keeps businesses that have a website and a public email, are open, and sit in a
mid-size band of reviews (not tiny, not huge chains). Skips anything already in
leads/all-leads.csv, writes today's file, appends to the master list, and pushes
to a Google Sheet if the GOOGLE_SERVICE_ACCOUNT_JSON and LEADS_SHEET_ID secrets exist.
"""
import csv
import datetime
import json
import os
import sys

csv.field_size_limit(10**8)
here = os.path.dirname(os.path.abspath(__file__))
raw_path = sys.argv[1]
min_reviews = int(os.environ.get("MIN_REVIEWS", "15"))
max_reviews = int(os.environ.get("MAX_REVIEWS", "2500"))

FIELDS = ["date", "business", "category", "query_id", "website", "email", "phone",
          "rating", "reviews", "address", "maps_link"]
SKIP_EMAIL = ("example.", "sentry", "wixpress", "@domain", "noreply", "no-reply", ".png", ".jpg")

master = os.path.join(here, "leads", "all-leads.csv")
seen = set()
if os.path.exists(master):
    with open(master, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            seen.add(r["maps_link"])
            seen.add(r["website"].lower().rstrip("/"))

today = datetime.date.today().isoformat()
rows = []
with open(raw_path, encoding="utf-8") as f:
    for r in csv.DictReader(f):
        site = (r.get("website") or "").strip()
        emails = [e.strip() for e in (r.get("emails") or "").replace(";", ",").split(",") if "@" in e]
        emails = [e for e in emails if not any(s in e.lower() for s in SKIP_EMAIL)]
        try:
            reviews = int(float(r.get("review_count") or 0))
        except ValueError:
            reviews = 0
        status = (r.get("status") or "").lower()
        if not site or not emails or "closed" in status:
            continue
        if not (min_reviews <= reviews <= max_reviews):
            continue
        key_site = site.lower().rstrip("/")
        if r.get("link") in seen or key_site in seen:
            continue
        seen.update([r.get("link"), key_site])
        rows.append({
            "date": today, "business": r.get("title", ""), "category": r.get("category", ""),
            "query_id": r.get("input_id", ""), "website": site, "email": emails[0],
            "phone": r.get("phone", ""), "rating": r.get("review_rating", ""), "reviews": reviews,
            "address": r.get("address", ""), "maps_link": r.get("link", ""),
        })

os.makedirs(os.path.join(here, "leads"), exist_ok=True)
with open(os.path.join(here, "leads", f"{today}.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=FIELDS)
    w.writeheader()
    w.writerows(rows)
new_master = not os.path.exists(master)
with open(master, "a", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=FIELDS)
    if new_master:
        w.writeheader()
    w.writerows(rows)
print(f"{len(rows)} new leads saved to whence/leads/{today}.csv")

creds = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
sheet_id = os.environ.get("LEADS_SHEET_ID")
if creds and sheet_id and rows:
    import gspread
    gc = gspread.service_account_from_dict(json.loads(creds))
    sh = gc.open_by_key(sheet_id)
    tab = os.environ.get("LEADS_SHEET_TAB", "Maps Leads")
    try:
        ws = sh.worksheet(tab)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=tab, rows=1000, cols=len(FIELDS))
        ws.append_row(FIELDS)
    ws.append_rows([[str(r[k]) for k in FIELDS] for r in rows], value_input_option="USER_ENTERED")
    print(f"Pushed {len(rows)} rows to the '{tab}' tab of the leads sheet")
elif rows:
    print("No Google Sheet secrets set, so leads were only saved in the repo")
