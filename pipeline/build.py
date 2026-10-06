#!/usr/bin/env python3
"""Build the buying-window event table and per-trade lists. Writes site/data/.

One row per CHANGE EVENT at a Minneapolis-area business: something public happened
that means the business is choosing vendors right now. The proof case is Joel Oine
(Blue Vector Bookkeeping, 2026-10-05): one row of a permit list, Evergreen Cafe,
became a meeting inside a day, because a business mid-build-out has "no existing
bookkeeping relationship to displace". The signals and their traps come from
~/Desktop/on-the-house/drafts/permits/blue-vector-enrichment/README.md and the
regexes from ~/Desktop/on-the-house/pipeline/permits/build2.py (both 10/04-10/05).

Sources, all free and keyless:
  * Minneapolis CCS_Permits        commercial build-outs + wrecking permits (live)
  * Minneapolis On_Sale_Liquor     new liquor licenses (numbers are sequential)
  * Minneapolis Food_Inspections   first-ever inspection of a kitchen = just opened
  * MN DEED WARN notices           read from the bricks layer, which caches the PDFs
                                   (the DEED listing needs a visible browser to
                                   refresh, see bricks/scripts/pull_deed_warn.py)

Run:  python3 pipeline/build.py        (about a minute; caches raw pulls in pipeline/cache)
"""
from __future__ import annotations

import csv
import datetime as dt
import io
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from trades import TRADES, TRIGGERS  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "pipeline" / "cache"
OUT = ROOT / "site" / "data"
WARN_LAYER = Path.home() / "Desktop/bricks/website/api/_data/twincities_layoff_notices.json"
CBP = Path.home() / "Desktop/bricks/data/cbp_trades_twincities.json"

MPLS = "https://services.arcgis.com/afSMGVsC7QlRK1kZ/arcgis/rest/services"
TODAY = dt.date.today()
WINDOW_DAYS = 120            # how far back an event still counts as "right now"
# Liquor license numbers are sequential; above this they were first issued in 2026
# (measured 2026-10-05, blue-vector-enrichment/README.md). The status field is not a
# newness signal: the spring renewal batch is "Pending" too.
NEW_LIQUOR_ABOVE = 420000


def q(svc: str, where: str, fields: str = "*") -> list[dict]:
    out, off = [], 0
    while True:
        p = dict(where=where, outFields=fields, f="json", resultOffset=off,
                 resultRecordCount=2000, returnGeometry="false")
        req = urllib.request.Request(f"{MPLS}/{svc}/FeatureServer/0/query",
                                     data=urllib.parse.urlencode(p).encode())
        d = json.load(urllib.request.urlopen(req, timeout=60))
        if "error" in d:
            raise SystemExit(f"{svc}: {d['error']}")
        fs = [f["attributes"] for f in d.get("features", [])]
        out += fs
        if not d.get("exceededTransferLimit") or not fs:
            return out
        off += len(fs)


def record_url(svc: str, field: str, value: str) -> str:
    """The city's own record, as a readable page on the city's ArcGIS server."""
    return (f"{MPLS}/{svc}/FeatureServer/0/query?" +
            urllib.parse.urlencode({"where": f"{field}='{value}'", "outFields": "*", "f": "html"}))


def day(ms) -> dt.date | None:
    return dt.datetime.fromtimestamp(int(ms) / 1000, dt.timezone.utc).date() if ms else None


SUF = {"AVENUE": "AVE", "STREET": "ST", "ROAD": "RD", "BOULEVARD": "BLVD", "PARKWAY": "PKWY",
       "DRIVE": "DR", "PLACE": "PL", "LANE": "LN"}


def addr_key(a: str) -> str:
    a = re.sub(r"\s*#.*$", "", (a or "").upper()).replace(".", "")
    a = re.sub(r",.*$", "", a)
    return " ".join(SUF.get(x, x) for x in a.split()[:4])


def pretty(a: str) -> str:
    a = re.sub(r"\s+", " ", (a or "").strip())
    out = []
    for w in a.split(" "):
        u = w.upper()
        if u in ("N", "S", "E", "W", "NE", "SE", "NW", "SW"):
            out.append(u)
        elif re.fullmatch(r"\d+(ST|ND|RD|TH)", u):
            out.append(w.lower())
        else:
            out.append(w.capitalize())
    return " ".join(out)


def clean(s: str) -> str:
    s = re.sub(r"\s+", " ", s or "").strip()
    # drop the code-review boilerplate the city appends to every description
    s = re.split(r"(?i)\s*(certificate of occupancy required|special inspections required|const(ruction)? type:|occupancy:|20\d\d MN?SBC|building code:)", s)[0]
    s = re.sub(r"\s*(-\s*ACW|\((JJL|ACW|[A-Z]{2,4}(-\w+)?)\))\s*", " ", s)
    s = re.sub(r"\*{2,}", " ", s)
    s = re.sub(r"\s+", " ", s).strip(" -,;.")
    if sum(ch.isupper() for ch in s) > 0.6 * max(1, sum(ch.isalpha() for ch in s)):
        s = ". ".join(x.strip().capitalize() for x in s.split(". "))
    if len(s) > 160:
        cut = s[:160]
        s = (cut[:cut.rfind(". ") + 1] if cut.rfind(". ") > 60 else cut[:cut.rfind(" ")] + "…")
    return s


def name_case(n: str) -> str:
    n = re.sub(r"\s+", " ", n or "").strip()
    if n.isupper():
        n = " ".join(w if w in ("LLC", "INC", "BBQ", "MN", "MPLS", "II", "III") else w.capitalize() for w in n.split())
    return n


# ---- regexes carried from on-the-house/pipeline/permits/build2.py (10/04) ----
NOTRES = re.compile(r"-unit \d|unit \d+\b.*kitchen|condo|apartment|dwelling|\bdu\b|residential unit|single-family", re.I)
EXCL = re.compile(r"water damage|fire damage|vehicle damage|repair|roof|solar|window|parking|\bsign\b|signage|fire barrier|"
                  r"sprinkler|stair|elevator|balcon|facade|masonry|tuckpoint|not a building permit|drain tile|bleacher|"
                  r"siding|demo only|interior demo|abatement|antenna|cell tower|rooftop|canopy|retaining wall", re.I)
BUILDOUT = re.compile(r"tenant|t/i\b|\bti\b|build[- ]?out|white ?box|change of use|new (restaurant|cafe|coffee|bar|bakery|brewery|"
                      r"taproom|store|shop|salon|clinic|office|retail)|convert|restaurant|cafe|café|coffee|\bbar\b|brewery|"
                      r"taproom|bakery|retail|\bstore\b|\bshop\b|salon|\bspa\b|barber|clinic|dental|fitness|gym|studio|"
                      r"dispensary|cannabis|grocery|daycare|child ?care|assisted living|office", re.I)
SEGMENTS = [
    ("food", r"restaurant|cafe|café|coffee|\bbar\b|brewery|taproom|bakery|pizza|tavern|\bpub\b|ice cream|dining|kitchen|"
             r"taqueria|distillery|commissary|deli\b|food"),
    ("retail", r"retail|\bstore\b|\bshop\b|boutique|grocery|market\b|mercantile|showroom|gallery|florist|bookstore|"
               r"dispensary|cannabis|salon|\bspa\b|barber|nail|tattoo|gym|fitness|yoga|dance studio|convenience|pharmacy"),
    ("care", r"clinic|dental|medical|therapy|daycare|child ?care|assisted living|health"),
    ("office", r"office|conference|corporate|suite"),
]


def segment(c: str) -> str:
    for k, p in SEGMENTS:
        if re.search(p, c, re.I):
            return k
    return "other"


def tenant(c: str) -> str:
    for pat in (r"(?:suite|ste\.?)\s*\w+\s*[-–:,]\s*([A-Z][\w'&.]+(?: [A-Z&][\w'&.]*){0,4})",
                r"T/I\s*-\s*([A-Z][\w'&.]+(?: [A-Z&][\w'&.]*){0,4})",
                r"(?:Facility|Improvement|build ?out)\s*-\s*([A-Z][\w'&.]+(?: [A-Z&][\w'&.]*){0,4})"):
        m = re.search(pat, c or "")
        if m and not re.match(r"(?i)suite|const|certificate|occupancy|remodel|tenant|acw|level|floor|\d", m.group(1)):
            return m.group(1).strip(" .")
    return ""


NEW_TENANT = re.compile(r"tenant (improvement|finish|build|space)|t/i\b|\bti\b|build[- ]?out|white ?box|change of (use|occupancy|ownership)|"
                        r"new (restaurant|bar|tenant|cafe|café|coffee|bakery|brewery|taproom|store|shop|retail|salon|clinic|"
                        r"office|fitness|gym|cannabis|dispensary|child|dog|daycare|kitchen opening)|for (a )?new|future tenant|"
                        r"spec suite|convert|demising|first generation|vacant", re.I)

SEG_WORD = {"food": "restaurant, bar or café", "retail": "shop or storefront", "care": "clinic or care site",
            "office": "office", "other": "commercial space"}


# What KIND of business is opening, the first thing a reader looks for. Ordered: first hit wins.
BTYPES = [
    (r"cannabis|dispensar|\bthc\b", "Cannabis dispensary"),
    (r"adult day", "Adult day care"),
    (r"assisted living|memory care|senior living", "Assisted living"),
    (r"veterinar|animal hospital|\bpets?\b|\bdog|grooming", "Pet business"),
    (r"child ?care|daycare|day care|preschool|montessori|early learning", "Child care center"),
    (r"brewery|brewing|taproom|distill|winery", "Brewery or taproom"),
    (r"bakery|bakehouse|donut|doughnut|patisserie", "Bakery"),
    (r"coffee|espresso|\bcaf[eé]\b|tea house|boba", "Coffee shop or café"),
    (r"fro ?yo|frozen yogurt|ice cream|gelato|creamery", "Dessert shop"),
    (r"pizz", "Pizza place"),
    (r"golf|\bputt|pickleball|bowling|arcade|billiard|axe throw|escape room|entertainment", "Entertainment venue"),
    (r"cinema|theater|theatre|gallery", "Theater or gallery"),
    (r"tavern|\bpub\b|saloon|lounge|sports bar|\bbar\b|cocktail|speakeasy", "Bar"),
    (r"restaurant|grill|kitchen\b|diner|eatery|bistro|taqueria|tacos?\b|sushi|ramen|bbq|barbe?que|burger|cucina|"
     r"cantina|gastro|cajun|antojitos|mexican|italian|ethiopian|thai\b|pho\b|noodle|deli\b|sandwich|chicken|wings|"
     r"steak|food hall|food court|street food|cuisine", "Restaurant"),
    (r"liquor store|liquors?\b|wine shop|bottle shop", "Liquor store"),
    (r"tobacco|vape|vapor|smoke shop", "Tobacco or vape shop"),
    (r"grocery|supermarket|mercado|market\b|halal|carniceria|food store|convenience", "Grocery or market"),
    (r"fitness|\bgym\b|yoga|pilates|crossfit|boxing|martial|climbing|barre|cycle studio", "Gym or fitness studio"),
    (r"salon|barber|\bhair\b|\bspa\b|nail|lash|brow|beauty|med ?spa|tattoo", "Salon or spa"),
    (r"dental|dentist|orthodont", "Dental office"),
    (r"clinic|medical|chiropract|physical therap|urgent care|optometr|pharmacy|dialysis|imaging|behavioral|therapy", "Clinic"),
    (r"event (center|venue|space)|banquet|ballroom", "Event venue"),
    (r"hotel|motel|\binn\b", "Hotel"),
    (r"\bbank\b|credit union|wells fargo|us bank|chase bank", "Bank branch"),
    (r"office|corporate|co-?working|state farm|insurance", "Office"),
    (r"retail|store|shop|boutique|showroom|mercantile", "Shop"),
]
SEG_TYPE = {"food": "Restaurant or bar", "retail": "Shop", "care": "Clinic", "office": "Commercial space", "other": "Commercial space"}


def btype(e: dict) -> str:
    if e["event"] == "warn":
        return "Employer closing" if e["stage"].startswith("Closing") else "Employer cutting jobs"
    if e["event"] == "wrecking":
        return "Office building coming down" if re.search(r"office", e["detail"], re.I) else "Commercial building coming down"
    d = e["detail"] if e["event"] == "buildout" else ""
    into = re.search(r"\b(?:into|convert(?:ed)? to) (?:an? )?(?:new )?(.{3,40})", d, re.I)  # "convert restaurant into a nail salon"
    for text in (e["name"], into.group(1) if into else "", d):
        for pat, label in BTYPES:
            if text and re.search(pat, text, re.I):
                return label
    if re.search(r"kitchenette", d, re.I):
        return "Commercial space"  # an office kitchenette is not a restaurant
    if e["event"] == "first_inspection":
        return "Restaurant" if e["segment"] == "food" else "Grocery or market"
    if e["event"] == "liquor":
        return "Restaurant or bar"
    return SEG_TYPE.get(e["segment"], "Commercial space")


def buildouts_and_wrecking() -> list[dict]:
    since = TODAY - dt.timedelta(days=WINDOW_DAYS)
    rows = q("CCS_Permits",
             f"permitType IN ('Commercial','Wrecking') AND (issueDate >= date '{since}' OR completeDate >= date '{since}')")
    (CACHE / "ccs_permits.json").write_text(json.dumps(rows))
    ev = []
    for x in rows:
        if x["status"] in ("Cancelled", "Expired", "Withdrawn"):
            continue
        c = clean(x.get("comments") or "")
        issued, done = day(x.get("issueDate")), day(x.get("completeDate"))
        url = record_url("CCS_Permits", "permitNumber", x["permitNumber"])
        if x["permitType"] == "Wrecking":
            if x["occupancyType"] not in ("Comm", "Mixed", "MFD", "3to4"):
                continue  # houses are in Demolition Notice; this list is for commercial buyers
            open_ = x["status"] != "Closed"
            ev.append(dict(event="wrecking", segment="", name="", address=pretty(x["Display"]), city="Minneapolis",
                           date=str(issued if open_ else (done or issued)),
                           stage="Permit open, building still standing" if open_ else "Torn down",
                           detail=c or "Wrecking permit", by=x.get("applicantName") or "", source="Minneapolis wrecking permit",
                           source_url=url, ref=x["permitNumber"]))
            continue
        if x["occupancyType"] not in ("Comm", "Mixed") or x["workType"] not in ("Remodel", "New", "Addition", "UnitFinish"):
            continue
        if not BUILDOUT.search(c) or EXCL.search(c) or NOTRES.search(c):
            continue
        if re.search(r"school|classroom|hospital|police|fire station|church|manufactur|cultivation|parking ramp|"
                     r"warehouse racking|bathroom|restroom|locker room|inspection only|bedroom|religious", c, re.I):
            continue
        seg = segment(c)
        new = bool(NEW_TENANT.search(re.sub(r"(?i)\bno change of \w+", "", c)))
        if seg in ("office", "other") and not new:
            continue  # an existing office redoing its own space is not a new buyer
        if re.search(r"court ?room|county|city of|federal|state of", c, re.I):
            continue
        if x["status"] == "Closed":
            stage, date = "Construction done, opening now", done or issued
        elif x.get("milestone") == "Final Inspection":
            stage, date = "Final inspection, opening soon", issued
        else:
            stage, date = "Under construction", issued
        if date < since:
            continue
        ev.append(dict(event="buildout", segment=seg, kind="New tenant" if new else "Remodel", name=tenant(c), address=pretty(x["Display"]), city="Minneapolis",
                       date=str(date), stage=stage, detail=c, by=x.get("applicantName") or "",
                       source="Minneapolis building permit", source_url=url, ref=x["permitNumber"]))
    return ev


def liquor() -> list[dict]:
    rows = q("On_Sale_Liquor", "1=1")
    (CACHE / "on_sale_liquor.json").write_text(json.dumps(rows))
    since = TODAY - dt.timedelta(days=WINDOW_DAYS)
    seen, ev = set(), []
    for l in rows:
        n = l["licenseNumber"]
        if n in seen or int(re.sub(r"\D", "", n) or 0) <= NEW_LIQUOR_ABOVE:
            continue
        seen.add(n)
        issued = day(l.get("issueDate"))
        pending = l["licenseStatus"] == "Pending"
        if not pending and (not issued or issued < since):
            continue
        ev.append(dict(event="liquor", segment="food", name=(l["licenseName"] or "").strip(),
                       address=pretty(l["address"] or ""), city="Minneapolis", date=str(issued or ""),
                       stage="License pending, not open yet" if pending else "License approved",
                       detail=f"New on-sale liquor license, number {n}",
                       by="", source="Minneapolis liquor license", source_url=record_url("On_Sale_Liquor", "licenseNumber", n),
                       ref=n))
    return ev


def first_inspections() -> list[dict]:
    # a kitchen is new if it has no inspection on file since 2024-01-01 before this one
    rows = q("Food_Inspections", "YearOfInspection>=2024",
             "HealthFacilityIDNumber,BusinessName,FacilityCategory,DateOfInspection,FullAddress,InspectionType")
    first: dict[str, tuple] = {}
    for f in rows:
        d, k = day(f["DateOfInspection"]), f["HealthFacilityIDNumber"]
        if d and (k not in first or d < first[k][0]):
            first[k] = (d, f)
    since = TODAY - dt.timedelta(days=WINDOW_DAYS)
    ev = []
    for k, (d, f) in first.items():
        cat = f["FacilityCategory"] or ""
        if d < since or cat not in ("RESTAURANT", "GROCERY"):
            continue
        if re.search(r"child ?care|daycare|day care|school|senior|academy|church|hospital|clinic|head start",
                     f["BusinessName"] or "", re.I):
            continue
        ev.append(dict(event="first_inspection", segment="food" if cat == "RESTAURANT" else "retail",
                       name=(f["BusinessName"] or "").strip(), address=pretty(f["FullAddress"] or ""), city="Minneapolis",
                       date=str(d), stage="Open now",
                       detail=f"First-ever city health inspection of this {'kitchen' if cat == 'RESTAURANT' else 'grocery'}",
                       by="", source="Minneapolis food inspection",
                       source_url=record_url("Food_Inspections", "HealthFacilityIDNumber", k), ref=k))
    return ev


def warn() -> list[dict]:
    d = json.loads(WARN_LAYER.read_text())
    ev = []
    for r in d["rows"]:
        if not r.get("in_seven_counties") or r.get("revision") or not r.get("notice_date"):
            continue
        since = str(TODAY - dt.timedelta(days=WINDOW_DAYS))
        if r["notice_date"] < since and (r.get("effective_date") or "") < str(TODAY):
            continue
        eff = r.get("effective_date")
        stage = ("Closing" if r.get("kind") == "closure" else "Layoffs") + (f" on {eff}" if eff else "")
        n = r.get("employees_stated")
        ev.append(dict(event="warn", segment="", name=r["employer"], address=r.get("site_address") or "",
                       city=r.get("site_city") or "", date=r["notice_date"], stage=stage,
                       detail=(f"{n} jobs stated in the notice" if n else "Layoff notice filed with the state"),
                       by="", source="MN DEED layoff (WARN) notice", source_url=r["notice_url"], ref=r["notice_url"]))
    return ev


def main() -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    events = buildouts_and_wrecking() + liquor() + first_inspections() + warn()
    events.sort(key=lambda e: (e["date"] or "0000"), reverse=True)

    # name a build-out by the license at the same address when the permit gives none
    names = {}
    for e in events:
        if e["event"] in ("liquor", "first_inspection") and e["name"]:
            names.setdefault(addr_key(e["address"]), e["name"])
    for e in events:
        # only where the build-out could be that same place: a daycare build-out at a
        # former restaurant's address must not take the restaurant's name
        if e["event"] == "buildout" and not e["name"] and e["segment"] in ("food", "other") \
                and addr_key(e["address"]) in names:
            e["name"] = names[addr_key(e["address"])]
            e["segment"] = "food"
    for e in events:
        e["name"] = name_case(e["name"])
        e["by"] = name_case(e["by"])
        e["type"] = btype(e)

    cbp = {t["naics"]: t for t in json.loads(CBP.read_text())["trades"]}
    trades = []
    for t in TRADES:
        rows = [e for e in events if any(e["event"] == ev and (not segs or e["segment"] in segs)
                                         for ev, segs in t["triggers"])]
        if not rows:
            continue
        slug = t["slug"]
        c = cbp.get(t["naics"])
        trades.append(dict(slug=slug, name=t["name"], naics=t["naics"], group=t["group"],
                           metro_firms=c["businesses_now"] if c else None,
                           why={ev: t["why"].get(ev, "") for ev, _ in t["triggers"]},
                           triggers=[[ev, segs] for ev, segs in t["triggers"]], count=len(rows)))
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["date", "type of business", "what happened", "stage", "business", "address", "city", "details", "filed by", "source", "source link"])
        for e in rows:
            w.writerow([e["date"], e["type"], TRIGGERS[e["event"]]["label"], e["stage"], e["name"], e["address"], e["city"],
                        e["detail"], e["by"], e["source"], e["source_url"]])
        (OUT / f"{slug}.csv").write_text(buf.getvalue())

    counts = {k: sum(e["event"] == k for e in events) for k in TRIGGERS}
    latest = {k: max((e["date"] for e in events if e["event"] == k and e["date"]), default="") for k in TRIGGERS}
    payload = dict(built=str(TODAY), window_days=WINDOW_DAYS, triggers=TRIGGERS, counts=counts, latest=latest,
                   trades=trades, events=events)
    (OUT / "events.json").write_text(json.dumps(payload, separators=(",", ":"), ensure_ascii=False))
    print("events", len(events), counts)
    print("latest", latest)
    print("trades mapped", len(trades), "of", len(TRADES))


if __name__ == "__main__":
    main()
