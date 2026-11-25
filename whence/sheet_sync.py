"""Connect the GitHub scraper to the Whence Lead Crawler sheet.

  python sheet_sync.py queries OUT.txt   Build today's searches from the sheet's
                                         "Maps Config" tab (Active rows), plus the
                                         next batch from lead-queries.txt.
  python sheet_sync.py push RESULTS.csv  Filter the scraper results and append new
                                         leads to the "Maps Leads" tab, in its columns.

Needs the secrets GOOGLE_SERVICE_ACCOUNT_JSON and LEADS_SHEET_ID. Without them it
only uses lead-queries.txt and writes the leads to a CSV kept with the run.
"""
import csv
import datetime
import json
import os
import re
import sys

csv.field_size_limit(10**8)
HERE = os.path.dirname(os.path.abspath(__file__))
TODAY = datetime.date.today().isoformat()
PLAN = os.path.join(HERE, "..", "run", "plan.json")
DEFAULT_MIN_REVIEWS = int(os.environ.get("MIN_REVIEWS", "50"))
MAX_REVIEWS = int(os.environ.get("MAX_REVIEWS", "5000"))
ROTATION = int(os.environ.get("ROTATION_BATCH", "4"))
SKIP_EMAIL = ("example.", "sentry", "wixpress", "@domain", "noreply", "no-reply",
              ".png", ".jpg", ".webp", "@2x", "godaddy", "yourname", "email@")
# Businesses that rarely buy brand work: resellers, chains' outlets, utilities, public bodies.
SKIP_CATEGORIES = ("wholesaler", "supplier", "distributor", "pharmacy", "chemist", "medical store",
                   "atm", "bank", "government", "petrol", "gas station",
                   "warehouse", "manufacturer", "courier")
CHAIN_SITE = re.compile(r"/stores?/|store-?locator|locator|utm_source=(google_)?gmb|utm_source=locator|"
                        r"^https?://(stores?|locations?|outlets?)\.|-stores?\.", re.I)
VALID_EMAIL = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.([a-z]{2}|com|org|net|io|store|shop|studio|design|boutique|life|biz|info|xyz|online|site|club|world|fashion|beauty|health|clinic|care|app|ai)$", re.I)
MAPS_COLUMNS = ["Date added", "Search", "Name", "Category", "Address", "Location searched",
                "Phone", "Website", "Email", "Email source", "Rating", "Reviews",
                "Google Maps link", "Place ID", "Status", "Notes", "Marketing need (0-10)",
                "Gaps found", "Outreach stage", "Last outreach date", "Email thread"]


def sheet():
    creds, sheet_id = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON"), os.environ.get("LEADS_SHEET_ID")
    if not (creds and sheet_id):
        return None
    import gspread
    return gspread.service_account_from_dict(json.loads(creds)).open_by_key(sheet_id)


def norm_site(url):
    url = (url or "").lower().strip()
    url = re.sub(r"^https?://", "", url)
    url = re.sub(r"^www\.", "", url)
    return url.split("/")[0]


def rotation_batch(count):
    with open(os.path.join(HERE, "lead-queries.txt"), encoding="utf-8") as f:
        qs = [q.strip() for q in f if q.strip() and not q.startswith("#")]
    if not qs or count <= 0:
        return []
    start = (datetime.date.today().toordinal() * count) % len(qs)
    return [qs[(start + i) % len(qs)] for i in range(min(count, len(qs)))]


def build_queries(out_path):
    plan = []  # each: search text, location, min reviews, depth, config row
    custom = os.environ.get("CUSTOM_QUERIES", "").strip()
    sh = sheet()
    if custom:
        for q in custom.split(";"):
            if q.strip():
                loc = q.split(" in ", 1)[1].strip() if " in " in q else ""
                plan.append({"search": q.strip(), "location": loc, "min": DEFAULT_MIN_REVIEWS, "depth": 1})
    else:
        if sh:
            rows = sh.worksheet("Maps Config").get_all_values()
            for i, r in enumerate(rows[1:], start=2):
                r += [""] * 6
                kind, loc, maxr, active, _, minr = r[:6]
                if not kind.strip() or active.strip().upper() != "TRUE":
                    continue
                depth = {"20": 1, "40": 2, "60": 3}.get(maxr.strip(), 1)
                mn = int(minr) if minr.strip().isdigit() else DEFAULT_MIN_REVIEWS
                plan.append({"search": f"{kind.strip()} in {loc.strip()}", "location": loc.strip(),
                             "min": mn, "depth": depth, "config_row": i})
        for q in rotation_batch(ROTATION):
            loc = q.split(" in ", 1)[1] if " in " in q else ""
            plan.append({"search": q, "location": loc, "min": DEFAULT_MIN_REVIEWS, "depth": 1})
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        for i, p in enumerate(plan):
            f.write(f"{p['search']} #!#q{i}\n")
    with open(PLAN, "w", encoding="utf-8") as f:
        json.dump(plan, f)
    depth = max([p["depth"] for p in plan] or [1])
    print(f"{len(plan)} searches today (depth {depth}):")
    for p in plan:
        print(" -", p["search"])
    gh_out = os.environ.get("GITHUB_OUTPUT")
    if gh_out:
        with open(gh_out, "a") as f:
            f.write(f"depth={depth}\n")


def known_leads(sh):
    sites, emails, places, names = set(), set(), set(), set()
    if not sh:
        return sites, emails, places, names
    for tab in ("Maps Leads", "India", "International", "Coaches"):
        try:
            rows = sh.worksheet(tab).get_all_values()
        except Exception:
            continue
        if not rows:
            continue
        head = [h.strip().lower() for h in rows[0]]
        for r in rows[1:]:
            rec = dict(zip(head, r))
            for k, v in rec.items():
                if "website" in k and v:
                    sites.add(norm_site(v))
                if "email" in k and "@" in v:
                    emails.add(v.strip().lower())
            if rec.get("place id"):
                places.add(rec["place id"].strip())
            if rec.get("name"):
                names.add(rec["name"].strip().lower())
    return sites, emails, places, names


def push(results_path):
    with open(PLAN, encoding="utf-8") as f:
        plan = json.load(f)
    sh = sheet()
    sites, emails, places, names = known_leads(sh)
    new = []
    with open(results_path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            qid = (r.get("input_id") or "").lstrip("q")
            p = plan[int(qid)] if qid.isdigit() and int(qid) < len(plan) else {"search": "", "location": "", "min": DEFAULT_MIN_REVIEWS}
            site = (r.get("website") or "").strip()
            found = [e.strip() for e in re.split(r"[,;\s]+", r.get("emails") or "") if "@" in e]
            found = [e for e in found if not any(s in e.lower() for s in SKIP_EMAIL)]
            try:
                reviews = int(float(r.get("review_count") or 0))
            except ValueError:
                reviews = 0
            if not site or not found or "closed" in (r.get("status") or "").lower():
                continue
            if any(w in (r.get("category") or "").lower() for w in SKIP_CATEGORIES):
                continue
            # A store page inside a bigger site (e.g. /stores/..., store locators) means a chain outlet.
            if CHAIN_SITE.search(site):
                continue
            found = [e for e in found if VALID_EMAIL.match(e)]
            if not found:
                continue
            if not (p["min"] <= reviews <= MAX_REVIEWS):
                continue
            pid, name, email = (r.get("place_id") or "").strip(), (r.get("title") or "").strip(), found[0].lower()
            if norm_site(site) in sites or email in emails or (pid and pid in places) or name.lower() in names:
                continue
            sites.add(norm_site(site)); emails.add(email); names.add(name.lower())
            if pid:
                places.add(pid)
            rating = r.get("review_rating") or ""
            try:
                rating = f"{float(rating):.1f}"
            except ValueError:
                pass
            new.append([TODAY, p["search"], name, r.get("category", ""), r.get("address", ""),
                        p["location"], r.get("phone", ""), site, email, "Business website",
                        rating, str(reviews), r.get("link", ""), pid, "New",
                        "Source: Google Maps scraper on GitHub", "", "", "", "", ""])

    os.makedirs(os.path.join(HERE, "..", "run"), exist_ok=True)
    with open(os.path.join(HERE, "..", "run", f"new-leads-{TODAY}.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(MAPS_COLUMNS)
        w.writerows(new)

    if not sh:
        print(f"{len(new)} new leads. Sheet secrets not set, so they are only in the run's CSV.")
        return
    if new:
        ws = sh.worksheet("Maps Leads")
        ws.append_rows(new, value_input_option="RAW", table_range="A1")
    used = sorted({p["config_row"] for p in plan if "config_row" in p})
    if used:
        cfg = sh.worksheet("Maps Config")
        cfg.batch_update([{"range": f"E{row}", "values": [[TODAY]]} for row in used])
    print(f"Added {len(new)} new leads to the Maps Leads tab")
    for row in new:
        print(f" - {row[2]} ({row[5]}): {row[8]}")


if __name__ == "__main__":
    cmd, arg = sys.argv[1], sys.argv[2]
    if cmd == "queries":
        build_queries(arg)
    elif cmd == "push":
        push(arg)
    else:
        sys.exit("usage: sheet_sync.py queries OUT.txt | push RESULTS.csv")
