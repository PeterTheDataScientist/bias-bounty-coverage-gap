"""Step 28. NOAA NCEI Storm Events: flood deaths and low-water crossings in the challenge's south-central Texas region.

    python ncei_events.py                    check the 90 NOAA files (downloading any that are missing), then the analysis
    python ncei_events.py --download-only    the files only
    python ncei_events.py --ncei-dir DIR     read the NOAA files from DIR instead of raw/ncei/ (NCEI_DIR=DIR is the same);
                                             a file missing there is downloaded into DIR
    python ncei_events.py --results DIR      write the shipped copies to DIR instead of ../results/ncei/
    python ncei_events.py --refresh          the files NCEI serves today instead of the entry's (the numbers may change)

Stage 1 (files): the bulk CSV files for 1996 to LAST_YEAR (details, fatalities, locations: 90 files, 337 MB) from
https://www.ncei.noaa.gov/pub/data/swdi/stormevents/csvfiles/. ../results/ncei/ncei_manifest.json, shipped with the
repository, gives the URL, retrieval time (UTC), byte count and sha256 of every file the entry read; the run copies it
to raw/ncei/ncei_manifest.json and checks every file against it. A missing file is downloaded from its URL and checked
the same way. A file that differs stops the run: NCEI replaces a year's file when it corrects it (the file name carries
its creation date). --refresh lists the directory again, fetches the newest version of each year's files and writes a
new raw/ncei/ncei_manifest.json, which then also replaces ../results/ncei/ncei_manifest.json.

Stage 2 (analysis, deterministic: no randomness, no clock in any output):
 1. Texas Flash Flood and Flood events, 1996 to LAST_YEAR, in the region's counties (the counties holding the challenge's
    south-central-tx tracts; GEOID characters 3 to 5). County-coded events use CZ_FIPS; the few zone-coded ones (1996 to
    2008) use the county whose Storm Events name equals the zone name. Counts per county and in total.
 2. Keyword flags on EVENT_NARRATIVE and EPISODE_NARRATIVE (the task's terms, with plural, hyphen and spacing variants),
    plus the fatality file's location (Vehicle/Towed Trailer).
 3. Matching to the 8,454 inventory crossings (work/lwc_unique.parquet): (a) coordinates, begin or end point within 1 km
    (coordinates used only when they fall within 25 km of the event's own county); (b) road names written in the
    narrative against the inventory road names in the same county (CR 628 = County Road 628, FM = RM = RR numbering,
    'Highway N' resolved only when the county lists one route type with that number), with stream names as corroboration
    and as a veto. A match is 'confirmed' only when the road is named in a sentence about a crossing, water over the road,
    a vehicle or driver, a stall, a barricade or something swept off the road; the crossing is singled out (the only
    listed crossing on that road in the county, or the only one whose stream the narrative names, or the only one on
    that road within 1 km of both event points); and nothing contradicts it (the full rule list is in the summary's
    confirmed_definition). Near misses worth a look are listed as 'ambiguous' with the reasons; weaker links are only
    counted. Every confirmed match carries a grade (A: two or more checks agree; B: one).
 4. For each matched crossing: inventory ID, road, county, Overture segment and flags (work/lwc_unique.parquet),
    careful-set membership (v4_common.careful_set(), the selection core_numbers.py uses, and the crossing-to-area links
    that examples.py uses: work/cuts_plus_strict.parquet and work/edges_plus_strict.parquet).
Outputs: work/ncei_events_region.csv (one row per region event, no narrative text), work/ncei_crossing_matches.csv
(confirmed rows first, then ambiguous; excerpts of at most 25 words), work/ncei_summary.json (every quotable number with
its definition, per-county table, sources with sha256).
Then the four files this repository ships, in ../results/ncei/: the event table without the two columns that repeat
others (ncei_url is the event page of event_id; source_file is the details file of the event's YEAR in the manifest),
the match table with any personal name removed from its excerpts (names are looked for in each report's full event and
episode narratives: a name followed by an age, after a title such as Mr or Mrs, or after 'identified as' or 'named'),
the summary and the manifest.
Licence: NOAA data are works of the US federal government, public domain in the United States.
"""
import sys, os, re, json, time, hashlib, datetime, shutil, argparse, urllib.request
from difflib import SequenceMatcher
import common
from common import HERE, TRACTS, arg_path, need

RAW = os.path.join(HERE, "raw", "ncei")             # the run's copy of the manifest, and the directory listing (--refresh)
WORK = os.path.join(HERE, "work")
NCEI_DIR = common.NCEI_DIR                         # the NOAA files themselves (default raw/ncei/)
SHIPPED = common.NCEI_MANIFEST                     # ../results/ncei/ncei_manifest.json, the files the entry read
RESULTS = os.path.join(os.pardir, "results", "ncei")
BASE = "https://www.ncei.noaa.gov/pub/data/swdi/stormevents/csvfiles/"
FIRST_YEAR, LAST_YEAR = 1996, 2025   # 2025 is the latest full year at retrieval (26 Sep 2026); the d2026 file is partial
TABLES = ("details", "fatalities", "locations")
MANIFEST = os.path.join(RAW, "ncei_manifest.json")
UA = {"User-Agent": "bias-bounty-research/1.0 (public-domain NOAA data, research use)"}


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def fetch(url, dest):
    for k in range(5):
        try:
            t = utc_now()
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=300) as r, open(dest + ".part", "wb") as f:
                while True:
                    b = r.read(1 << 20)
                    if not b: break
                    f.write(b)
            os.replace(dest + ".part", dest)
            return t
        except Exception as e:
            print("retry", k, url, e, file=sys.stderr, flush=True)
            time.sleep(5 * (k + 1))
    if os.path.exists(dest + ".part"):
        os.remove(dest + ".part")
    sys.exit(f"ncei_events.py: could not download {url} after 5 tries. NCEI may have replaced the file with a newer "
             "version (the name carries its creation date): python ncei_events.py --refresh fetches the current files, "
             "and the numbers may then differ from the entry's.")


def resolve_files():
    """List the NCEI directory and pick, for each table and year, the file NCEI serves now (newest creation date)."""
    listing = os.path.join(RAW, "csvfiles_index.html")
    t = fetch(BASE, listing)
    html = open(listing, encoding="utf-8", errors="replace").read()
    names = sorted(set(re.findall(r'href="(StormEvents_(details|fatalities|locations)-ftp_v1\.0_d(\d{4})_c(\d{8})\.csv\.gz)"', html)))
    pick = {}
    for fn, tab, yr, cr in names:
        yr = int(yr)
        if not FIRST_YEAR <= yr <= LAST_YEAR: continue
        if (tab, yr) not in pick or cr > pick[(tab, yr)][1]:
            pick[(tab, yr)] = (fn, cr)
    miss = [(tb, y) for tb in TABLES for y in range(FIRST_YEAR, LAST_YEAR + 1) if (tb, y) not in pick]
    if miss: raise SystemExit(f"files missing from the NCEI listing: {miss}")
    later = sorted({int(y) for _, _, y, _ in names if int(y) > LAST_YEAR})
    return dict(url=BASE, retrieved_utc=t, sha256=sha256(listing), file=os.path.relpath(listing, HERE),
                years_after_last_year_in_listing=later), {k: v[0] for k, v in pick.items()}


def download(refresh=False):
    """The files of the shipped manifest, each checked by sha256 and downloaded only when missing; with refresh, the
    files NCEI serves today (reusing any the entry read that are unchanged), recorded in a new raw/ncei/ncei_manifest.json."""
    os.makedirs(RAW, exist_ok=True)
    os.makedirs(NCEI_DIR, exist_ok=True)
    need(SHIPPED)
    pinned = json.load(open(SHIPPED))
    if refresh:
        listing, pick = resolve_files()
        old = {f["file"]: f for f in pinned.get("files", [])}
        files = []
        for (tab, yr), fn in sorted(pick.items(), key=lambda kv: (TABLES.index(kv[0][0]), kv[0][1])):
            dest = os.path.join(NCEI_DIR, fn)
            if fn in old and os.path.exists(dest) and sha256(dest) == old[fn]["sha256"]:
                files.append(old[fn]); continue
            t = fetch(BASE + fn, dest)
            files.append(dict(table=tab, year=yr, file=fn, url=BASE + fn, retrieved_utc=t, bytes=os.path.getsize(dest), sha256=sha256(dest)))
            print("downloaded", fn, files[-1]["bytes"], flush=True)
        man = dict(source="NOAA National Centers for Environmental Information (NCEI), Storm Events Database, bulk CSV files",
                   licence="Work of the US federal government: public domain in the United States",
                   format_doc=BASE + "Storm-Data-Bulk-csv-Format.pdf", first_year=FIRST_YEAR, last_year=LAST_YEAR,
                   directory_listing=listing, files=files)
        with open(MANIFEST, "w") as f:
            json.dump(man, f, indent=1)
        new = sorted(set(f["file"] for f in files) - set(old))
        print(f"--refresh: {len(new)} of {len(files)} files differ from the entry's (the manifest shipped in {SHIPPED})"
              + (": " + ", ".join(new) if new else "; the outputs should equal the entry's"), flush=True)
    else:
        shutil.copyfile(SHIPPED, MANIFEST)
        man = pinned
        for f in man["files"]:
            dest = os.path.join(NCEI_DIR, f["file"])
            if not os.path.exists(dest):
                print("downloading", f["file"], flush=True); fetch(f["url"], dest)
            h = sha256(dest)
            if h != f["sha256"]:
                sys.exit(f"ncei_events.py: {dest} has sha256 {h}; the entry read {f['sha256']} ({SHIPPED}). NCEI may have "
                         "replaced the file: python ncei_events.py --refresh fetches the current files, and the numbers may "
                         "then differ from the entry's.")
    return man


# ----------------------------------------------------------------------------------------------------------------------
# Stage 2: analysis
# ----------------------------------------------------------------------------------------------------------------------
EVENT_TYPES = ("Flash Flood", "Flood")
RADIUS_M = 1000.0      # coordinate match: begin or end point within 1 km of the crossing
FAR_M = 5000.0         # a named-road match more than 5 km from both event points and outside the event's mapped area is not confirmed
COUNTY_TOL_M = 25000.0 # event coordinates more than 25 km outside their own county are treated as unusable
NEAR_M = 2000.0        # a crossing pinned only as 'the only listed one on that road' must lie within 2 km of an event point or inside its area
VEHICLE_LOC = "Vehicle/Towed Trailer"
EVENT_URL = "https://www.ncei.noaa.gov/access/storm-events-database/event-details/{}"   # NCEI event page (the old eventdetails.jsp?id= link redirects here)
EXCERPT_WORDS = 25
# A personal name in a report, found by its context: followed by an age ('..., age 47', '..., 47,', '... (47)',
# '..., a 47-year-old'), after a title (Mr, Mrs, Ms, Miss), or after 'identified as' or 'named'. The shipped excerpts are
# cleared of any name found in their report (NAME_REMOVED in its place); the work/ tables keep the excerpts as extracted.
_W = r"[A-Z][a-z'\-]+"
_NAME1 = _W + r"(?:\s+[A-Z]\.?)?(?:\s+(?:Mc|O'|De\s|de\s)?" + _W + r"){0,2}"   # one to three words, middle initial allowed
_NAME = _W + r"(?:\s+[A-Z]\.?)?(?:\s+(?:Mc|O'|De\s|de\s)?" + _W + r"){1,2}"    # two or three words
PERSON = [re.compile(r"\b(" + _NAME1 + r"),?\s+(?:age|aged)\s+\d{1,3}\b"),
          re.compile(r"\b(" + _NAME + r"),\s+\d{1,3}\s*,"), re.compile(r"\b(" + _NAME + r")\s*\(\s*\d{1,3}\s*\)"),
          re.compile(r"\b(" + _NAME + r"),\s+(?:a|an)\s+\d{1,3}[- ]years?[- ]old"),
          re.compile(r"\b(?:Mr|Mrs|Ms|Miss)\.?\s+(" + _W + r"(?:\s+" + _W + r")?)"),
          re.compile(r"\b(?:identified as|named)\s+(" + _NAME + r")")]
NAME_REMOVED = "[name removed]"

# The task's search terms, with plural, hyphen and spacing variants. 'van' only in lower case (Van Zandt County).
KW = {
    "low_water_crossing": re.compile(r"\blow[\s-]*water[\s-]*(?:crossing|xing)s?\b", re.I),
    "water_over_road": re.compile(r"\bwater\s+(?:\w+\s+){0,3}?(?:over|across)\s+(?:the\s+|a\s+)?(?:road|roadway|street|highway|bridge|crossing)s?\b", re.I),
    "swept_away": re.compile(r"\b(?:swept|washed|carried)\s+(?:\w+\s+){0,2}?(?:away|off|downstream|into)\b", re.I),
    "vehicle": re.compile(r"(?i:\b(?:vehicles?|cars?|trucks?|pick-?ups?|suvs?|motorists?|automobiles?|sedans?|jeeps?)\b)|\bvans?\b"),
    "drove_into": re.compile(r"\b(?:drove|driven|driving)\s+(?:\w+\s+){0,3}?(?:into|through|across|onto)\b", re.I),
    "crossing": re.compile(r"\bcrossings?\b", re.I),
}
EXTRA = {
    "rescue_stranded_trapped": re.compile(r"\brescu\w*|\bstranded\b|\btrapped\b", re.I),
    # people, homes or vehicles cut off, stranded or trapped ('isolated' alone is mostly 'isolated rainfall totals')
    "cut_off_stranded_trapped": re.compile(
        r"\bcut\s+off\b|\bmarooned\b|"
        r"\b(?:residents|homes|houses|families|people|persons|community|communities|subdivisions?|neighbou?rhoods?|campers|ranch(?:es)?|households?)\b[^.;]{0,60}\b(?:isolated|stranded|trapped)\b|"
        r"\b(?:isolated|stranded|trapped)\b[^.;]{0,40}\b(?:residents|homes|houses|families|community|communities|subdivisions?|neighbou?rhoods?|households?)\b|"
        r"\bunable\s+to\s+(?:leave|get\s+out|get\s+home|reach\s+(?:their|his|her)\s+homes?)\b|\b(?:no|only)\s+(?:way|access|road|route)\s+(?:in|out|into)\b", re.I),
}
DEATH = re.compile(r"\bdrown\w*|\bdied\b|\bdeaths?\b|\bdead\b|\bdeceased\b|\bkill\w*|\bfatal\w*|\bbod(?:y|ies)\b|\bperish\w*|"
                   r"\bsuccumb\w*|\blost\s+(?:their|his|her)\s+li(?:fe|ves)\b|\b(?:not|neither|never)\b[^.;]{0,40}\bsurviv\w*", re.I)
# people at the site: a vehicle, driver or motorist, a rescue, someone stranded, trapped or cut off, or a death
PEOPLE = re.compile(KW["vehicle"].pattern + r"|(?i:\bdriv(?:er|ers)\b|\bmotorists?\b|\brescu\w*|\bstranded\b|\btrapped\b|\bcut\s+off\b|"
                    r"\b(?:man|men|woman|women|boys?|girls?|child|children|mother|father|husband|wife|famil(?:y|ies)|occupants?|"
                    r"passengers?|persons?|people|residents|teen\w*|victims?)\b)|(?i:" + DEATH.pattern + ")")
# words placing the incident AT a water crossing of the road (used to grade single-check matches)
SITE = re.compile("|".join(["(?i:" + KW[k].pattern + ")" for k in ("low_water_crossing", "water_over_road", "swept_away", "crossing")]) +
                  r"|(?i:\bbridges?\b|\bswept\b|\bwashed\b)")
DEATH_SHORT = 6        # in a narrative of at most 6 sentences death words anywhere count as near the match; else the previous, same or next 2 sentences
# A sentence describes an incident AT A ROAD SITE if it mentions a crossing, water over the road, a vehicle or driver,
# driving into water, a stall, a barricade, or something swept or washed off the road. 'Swept' alone is not enough
# ('swept off his roof'), nor is 'rescue' alone (homes are rescued too).
INCIDENT = re.compile("|".join(["(?i:" + KW[k].pattern + ")" for k in ("low_water_crossing", "water_over_road", "drove_into", "crossing")] +
                               [KW["vehicle"].pattern] +
                               [r"\bdrive\b|(?i:\bdriv(?:er|ers|ing|en)\b|\bdrove\b|\bmotorists?\b|\bstall\w*|\bbarricade\w*|\bbarriers?\b|"
                                r"\b(?:swept|washed)\s+(?:\w+\s+){0,2}?off\s+(?:of\s+)?(?:the\s+|a\s+)?(?:road|roadway|street|highway|bridge|crossing)s?\b)"]))
# a road written right after these words is a reference point ('east of Beck Road', 'intersection of X and Y', 'near X and Y'),
# not necessarily the flooded road
REFERENCE = re.compile(r"(?:\b(?:north|south|east|west|northeast|northwest|southeast|southwest|n|s|e|w|ne|nw|se|sw)\s+of|"
                       r"\bnear|\bfrom|\btoward|\btowards|\bpast|\bbetween|\bmiles?\s+of)\s*(?:the\s+)?$|"
                       r"\b(?:intersections?|corner|junction)\s+of\b[^.;]*$|\b(?:near|between|at)\s+(?:the\s+)?[^.;,]{0,60}\b(?:and|&)\s*(?:the\s+)?$|"
                       r"\bfrom\s+[^.;]{0,80}\bto\s*(?:the\s+)?$", re.I)
# 'off X' places a site beside road X ('crossing off Oltorf St'), unless something was swept, washed or driven off X
OFF_REF = re.compile(r"\boff\s*$", re.I)
OFF_MOVE = re.compile(r"\b(?:swept|washed|carried|forced|pushed|driven|drove|slid|went|ran|run)\s+(?:\w+\s+){0,2}?off\s*$", re.I)
# first road of an intersection pair 'at X and Y', where Y is itself a road ('at Walnut Grove road and Ricci Acres' is not a pair)
PAIR_BEFORE = re.compile(r"\bat\s+(?:the\s+)?$", re.I)
MAX_CANDIDATES = 3     # ambiguous matches on a road with more listed crossings than this: only the nearest 3 are listed
REF_RADIUS_M = 500.0   # a road written as a reference point is confirmed only if both event points lie within 500 m of its crossing
STREAM_SIMILAR = 0.85   # name parts at least this similar (difflib ratio) count as a spelling variant ('MOUNTIAN' v 'Mountain')

NUM = r"(\d{1,4}[A-Za-z]?)"
SEP = r"[ \t\-#]*"
ROUTE_RX = [  # order matters: each match is masked before the next pattern runs, generic 'Highway N' last
    ("CR", re.compile(r"\b(?:(?i:county\s+roads?|county\s+rds?\.?|co\.?\s+rds?\.?|co\.?\s+roads?)|C\.\s?R\.|CR)" + SEP + NUM + r"\b")),
    ("FMRM", re.compile(r"\b(?:(?i:farm[\s-]+to[\s-]+market(?:\s+roads?|\s+rds?\.?)?|farm\s+roads?|ranch[\s-]+to[\s-]+market(?:\s+roads?|\s+rds?\.?)?|"
                        r"ranch\s+roads?|ranch\s+rds?\.?)|F\.\s?M\.|R\.\s?M\.|FM|RM|RR)" + SEP + NUM + r"\b")),
    ("SH", re.compile(r"\b(?:(?i:state\s+highways?|state\s+hwys?\.?|texas\s+highway|texas\s+hwy\.?|state\s+road|state\s+route)|S\.\s?H\.|SH|TX|SR)" + SEP + NUM + r"\b")),
    ("US", re.compile(r"\b(?:(?i:u\.?\s?s\.?\s+highways?|u\.?\s?s\.?\s+hwys?\.?)|U\.S\.|US)" + SEP + NUM + r"\b")),
    ("IH", re.compile(r"\b(?:(?i:interstate(?:\s+highway)?)|IH|I)" + SEP + r"(\d{1,3})\b")),
    ("LOOP", re.compile(r"\b(?:(?i:loop)|LP)" + SEP + NUM + r"\b")),
    ("SPUR", re.compile(r"\b(?:(?i:spur)|SP)" + SEP + NUM + r"\b")),
    ("PR", re.compile(r"\b(?:(?i:park\s+road)|PR)" + SEP + NUM + r"\b")),
    ("HWY", re.compile(r"\b(?i:highways?|hwys?\.?)" + SEP + NUM + r"\b")),
]
CONT = re.compile(r"^(?:\s*(?:,|and|&|or)\s*)(\d{1,4}[A-Za-z]?)\b(?!\s*(?:inches|inch|in\b|feet|ft\b|foot|miles?|mph|homes?|people|persons|cars|vehicles|%|percent))", re.I)
SUFFIXES = (r"Road|Rd|Roads|Street|St|Drive|Dr|Lane|Ln|Trail|Trl|Parkway|Pkwy|Boulevard|Blvd|Avenue|Ave|Way|Circle|Cir|Court|Ct|Pass|"
            r"Path|Place|Pl|Terrace|Ter|Highway|Hwy|Pike|Cove|Cv|Trace|Row|Loop|Run|Bend|Ridge")
NAMEW = r"(?:[A-Z][A-Za-z'\.]*|\d{1,4}(?:st|nd|rd|th))"
PAIR_AFTER = re.compile(r"^[\s.,]*(?:and|&)\s+(?:the\s+)?(?:(?:(?:[A-Z][A-Za-z'\.]*|\d{1,4}(?:st|nd|rd|th))[ \-]+){1,4}(?i:" + SUFFIXES + r")\b|"
                        r"(?:CR|FM|RM|RR|SH|US|IH|I|Loop|Spur|(?i:county\s+road|farm[\s-]+to[\s-]+market|ranch\s+road|state\s+highway|highway|hwy))[\s\-#]*\d)")
CONN = r"(?:de|del|la|las|los|el)"
NAMED_RX = re.compile(r"\b((?:" + NAMEW + r"(?:[ \-]+" + CONN + r")?[ \-]+){1,5})(?i:(" + SUFFIXES + r"))\b\.?(?![ \-]*#?\d)")
STREAM_TYPES = r"Creek|River|Branch|Bayou|Draw|Fork|Slough|Arroyo|Canyon|Hollow"
STREAM_RX = re.compile(r"\b((?:" + NAMEW + r"[ \-]+){1,4})(?i:(" + STREAM_TYPES + r"))\b(?![ \-]+(?i:" + SUFFIXES + r")\b)")
# words that may precede a name inside a capitalised run without being part of it
STOP = set("""THE A AN ON AT ALONG NEAR ACROSS IN OF AND FROM TO OVER UNDER BETWEEN BOTH SEVERAL MANY NUMEROUS FLOODING FLOODED
FLASH WATER HEAVY RAIN THUNDERSTORMS POLICE SHERIFF EMERGENCY LAW OFFICIALS ALSO INCLUDING DOWNTOWN OFF ONTO INTO WITH WHILE
WHEN AFTER BEFORE DURING NORTHBOUND SOUTHBOUND EASTBOUND WESTBOUND CLOSED CLOSING REPORTS REPORTED MEDIA BROADCAST NEWS
THIS THAT THESE THOSE BLOCK FOR BY AS OR BUT HE SHE THEY IT HIS HER THEIR""".split())
DIRS = {"N", "S", "E", "W", "NE", "NW", "SE", "SW"}
STREAM_WORDS = {"CREEK", "RIVER", "BRANCH", "BAYOU", "DRAW", "FORK", "SLOUGH", "ARROYO", "CANYON", "HOLLOW"}
# numbered state and federal routes run for tens of km, so 'the only listed crossing on it in the county' is not enough on its own
LONG_ROUTES = {"FMRM", "SH", "US", "IH", "LOOP", "SPUR", "PR", "BUS", "HWY"}
ABBR = re.compile(r"\b(Rd|St|Dr|Ln|Ave|Blvd|Co|Hwy|Mt|Ft|Jr|Sr|Mr|Mrs|Ms|No|Pkwy|Trl|Cir|Ct|Ste|vs|approx|Mi|mi|U\.S|a\.m|p\.m)\.")


def sentences(text):
    """Split a narrative into sentences, keeping abbreviations and decimals intact. Returns [(start, end, sentence)]."""
    t = ABBR.sub(lambda m: m.group(1) + "\x00", text)
    t = re.sub(r"(\d)\.(\d)", "\\1\x01\\2", t)
    out, pos = [], 0
    for m in re.finditer(r"(?<=[.!?])\s+|\s*\|\s*|(?<=[a-z]{2}\.)(?=[A-Z])", t):
        out.append((pos, m.start(), t[pos:m.start()])); pos = m.end()
    out.append((pos, len(t), t[pos:]))
    return [(a, b, s.replace("\x00", ".").replace("\x01", ".").strip()) for a, b, s in out if s.strip()]


def num_norm(n):
    m = re.match(r"0*(\d+)([A-Za-z]?)$", n)
    return (m.group(1) or "0") + m.group(2).upper() if m else n.upper()


def name_words(s):
    from lwc_names import norm
    return [w for w in norm(s).split() if w not in DIRS]


def stream_words(s):
    s = re.sub(r"'S\b|'", "", str(s).upper())
    return [{"NORTH": "N", "SOUTH": "S", "EAST": "E", "WEST": "W"}.get(x, x) for x in re.sub(r"[^A-Z0-9 ]", " ", s).split()]


def extract_roads(sent):
    """Numbered routes and named roads written in one sentence: [(kind, key, raw, start, end)]."""
    out, masked = [], sent
    for cls, rx in ROUTE_RX:
        for m in list(rx.finditer(masked)):
            nums = [m.group(1)]
            if re.search(r"(?i)roads|rds|highways|hwys", m.group(0)):   # 'County Roads 258 and 268'
                rest = masked[m.end():]
                while True:
                    c = CONT.match(rest)
                    if not c: break
                    nums.append(c.group(1)); rest = rest[c.end():]
            for n in nums:
                out.append(("route", (cls, num_norm(n)), m.group(0).strip(), m.start(), m.end()))
        masked = rx.sub(lambda m: " " * len(m.group(0)), masked)
    for m in NAMED_RX.finditer(masked):
        words = name_words(m.group(1) + " " + m.group(2))
        if len(words) >= 2 and " ".join(words[:2]) != "LOW WATER":
            out.append(("named", tuple(words), (m.group(1) + m.group(2)).strip(), m.start(), m.end()))
    return out


def extract_streams(text):
    out = []
    for m in STREAM_RX.finditer(text):
        w = stream_words(m.group(1) + " " + m.group(2))
        if len(w) >= 2: out.append((tuple(w), (m.group(1) + m.group(2)).strip()))
    return out


def best_suffix(words, index):
    """Longest word-suffix of a narrative name run found in `index`. 'exact' if every word before it is a stop word."""
    for k in range(len(words) - 1):
        key = tuple(words[k:])
        if key in index:
            return key, ("exact" if all(w in STOP for w in words[:k]) else "partial")
    return None, None


def inv_route(s):
    from lwc_names import norm
    n = norm(s)
    m = re.search(r"\b(FM|RM|RR|SH|CR|US|IH|PR|LOOP|LP|SPUR|SP|BUS|BU|SR)\s*(\d+[A-Z]?)\b", n)
    if not m: return None
    cls = {"RM": "FMRM", "RR": "FMRM", "FM": "FMRM", "LP": "LOOP", "SP": "SPUR", "BU": "BUS", "SR": "SH"}.get(m.group(1), m.group(1))
    return (cls, num_norm(m.group(2)))


def aliases(road, seg_name, seg_refs, tier):
    """Inventory road string -> names to match: the string, its bracketed alternative ('CR 215 (PURGATORY RD)'), parts
    split at '/' or '&', and for crossings Overture confirms (tiers A and B) the Overture name and route refs."""
    from lwc_names import unnamed
    out = []
    if isinstance(road, str) and not unnamed(road):
        parts = [road] + re.findall(r"\(([^)]*)\)", road)
        base = re.sub(r"\([^)]*\)", " ", road)
        parts += [p for p in re.split(r"(?<!\d)/(?!\d)|&", base) if p.strip()]
        out += [(p.strip(), "inventory") for p in parts if p.strip()]
    if tier in ("A_name_verified", "B_unnamed_within_15m"):
        if isinstance(seg_name, str) and seg_name.strip(): out.append((seg_name.strip(), "overture"))
        if isinstance(seg_refs, str): out += [(r.strip(), "overture") for r in seg_refs.split("|") if r.strip()]
    return out


def excerpt(sent, offset=0, n=EXCERPT_WORDS):
    """At most n words of one sentence, centred on the character offset of the matched road."""
    toks = [(m.start(), m.group(0)) for m in re.finditer(r"\S+", sent)]
    if not toks: return ""
    i = max(k for k, (p, _) in enumerate(toks) if p <= max(offset, toks[0][0]))
    a = max(0, min(i - n // 2, len(toks) - n)); b = min(len(toks), a + n)
    s = " ".join(t for _, t in toks[a:b]).replace("\u2013", "-").replace("\u2014", "-")
    return ("..." if a > 0 else "") + s + ("..." if b < len(toks) else "")


def analyse(man):
    need(TRACTS, "work/lwc_all.parquet", "work/lwc_unique.parquet", "work/edges_plus_strict.parquet", "work/cuts_plus_strict.parquet")
    import numpy as np, pandas as pd, pyproj, shapely
    from scipy.spatial import cKDTree
    from lwc_names import unnamed
    from v4_common import careful_set

    def read(table, keep):
        out = []
        for f in man["files"]:
            if f["table"] != table: continue
            d = pd.read_csv(os.path.join(NCEI_DIR, f["file"]), dtype=str, keep_default_na=False, na_values=[""], low_memory=False)
            d = keep(d)
            d["source_file"] = f["file"]
            out.append(d)
        return pd.concat(out, ignore_index=True)

    # ---- 1. events ----
    TX = read("details", lambda d: d[d.STATE_FIPS.astype(float) == 48])
    name2fips = TX[TX.CZ_TYPE == "C"].groupby("CZ_NAME").CZ_FIPS.first().astype(int).to_dict()
    fips2name = {v: k for k, v in name2fips.items()}
    tr = pd.read_parquet(TRACTS, columns=["GEOID"])
    region = sorted(set(tr.GEOID.str[2:5].astype(int)))
    F = TX[TX.EVENT_TYPE.isin(EVENT_TYPES) & TX.YEAR.astype(int).between(FIRST_YEAR, LAST_YEAR)].copy()
    F["county_fips3"] = [int(f) if t == "C" else name2fips.get(n) for t, f, n in zip(F.CZ_TYPE, F.CZ_FIPS, F.CZ_NAME)]
    unmapped_zone = F[F.county_fips3.isna()]
    F = F[F.county_fips3.notna()].copy(); F["county_fips3"] = F.county_fips3.astype(int)
    F = F[F.county_fips3.isin(region)].copy()
    for c in ["DEATHS_DIRECT", "DEATHS_INDIRECT", "INJURIES_DIRECT", "INJURIES_INDIRECT"]:
        F[c] = F[c].fillna("0").astype(int)
    for c in ["BEGIN_LAT", "BEGIN_LON", "END_LAT", "END_LON"]:
        F[c] = pd.to_numeric(F[c], errors="coerce")
    F["EVENT_NARRATIVE"] = F.EVENT_NARRATIVE.fillna(""); F["EPISODE_NARRATIVE"] = F.EPISODE_NARRATIVE.fillna("")
    F["begin"] = [f"{ym[:4]}-{ym[4:6]}-{int(d):02d} {int(t) // 100:02d}:{int(t) % 100:02d}" for ym, d, t in zip(F.BEGIN_YEARMONTH, F.BEGIN_DAY, F.BEGIN_TIME)]
    F["event_id"] = F.EVENT_ID.astype(int)
    F = F.sort_values(["begin", "event_id"]).reset_index(drop=True)
    L = pd.read_parquet("work/lwc_all.parquet", columns=["src", "GEOID", "county_src"])
    L = L[L.GEOID.notna() & L.county_src.notna()]
    inv_names = L.groupby(L.GEOID.str[2:5].astype(int)).county_src.agg(lambda s: s.mode().iloc[0]).to_dict()
    F["county"] = [inv_names.get(c, fips2name.get(c, str(c)).title()) for c in F.county_fips3]
    F["deaths"] = F.DEATHS_DIRECT + F.DEATHS_INDIRECT
    F["injuries"] = F.INJURIES_DIRECT + F.INJURIES_INDIRECT

    FAT = read("fatalities", lambda d: d)
    FAT = FAT[FAT.EVENT_ID.astype(int).isin(set(F.event_id))].copy(); FAT["event_id"] = FAT.EVENT_ID.astype(int)
    fat_n = FAT.groupby("event_id").size(); fat_v = FAT[FAT.FATALITY_LOCATION == VEHICLE_LOC].groupby("event_id").size()
    fat_w = FAT[FAT.FATALITY_LOCATION == "In Water"].groupby("event_id").size()
    F["fatality_rows"] = F.event_id.map(fat_n).fillna(0).astype(int)
    F["fatality_rows_vehicle"] = F.event_id.map(fat_v).fillna(0).astype(int)
    F["fatality_rows_in_water"] = F.event_id.map(fat_w).fillna(0).astype(int)

    # ---- 2. keywords ----
    F["primary_text"] = np.where(F.EVENT_NARRATIVE.str.len() > 0, F.EVENT_NARRATIVE, F.EPISODE_NARRATIVE)
    F["narrative_source"] = np.where(F.EVENT_NARRATIVE.str.len() > 0, "event", np.where(F.EPISODE_NARRATIVE.str.len() > 0, "episode (event narrative empty)", "none"))
    for k, rx in list(KW.items()) + list(EXTRA.items()):
        F["kw_" + k] = F.EVENT_NARRATIVE.map(lambda s: bool(rx.search(s)))
        F["ep_" + k] = F.EPISODE_NARRATIVE.map(lambda s: bool(rx.search(s)))
        F["pr_" + k] = F.primary_text.map(lambda s: bool(rx.search(s)))
    kwcols = ["kw_" + k for k in KW]; epcols = ["ep_" + k for k in KW]
    F["any_term_event"] = F[kwcols].any(axis=1); F["any_term_episode"] = F[epcols].any(axis=1)
    F["candidate"] = F.any_term_event | F.any_term_episode | (F.fatality_rows_vehicle > 0)

    # ---- 3. crossings, distances ----
    U = pd.read_parquet("work/lwc_unique.parquet").reset_index(drop=True)
    U["crossing_id"] = U.src + ":" + U.src_id
    U["county3"] = U.COUNTYFP.astype(int)
    Ux, Uy = U.x.values, U.y.values
    tree = cKDTree(np.column_stack([Ux, Uy]))
    tf = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:3083", always_xy=True)
    for p in ("BEGIN", "END"):
        x, y = tf.transform(F[p + "_LON"].values, F[p + "_LAT"].values)
        F[p.lower() + "_x"] = x; F[p.lower() + "_y"] = y
    F["has_coords"] = F.begin_x.notna() & np.isfinite(F.begin_x)
    # coordinates are trusted only if the begin and end points lie within COUNTY_TOL_M of the event's own county
    T = pd.read_parquet(TRACTS, columns=["GEOID", "geometry"])
    tgeo = shapely.transform(shapely.from_wkb(T.geometry.values), lambda c: np.column_stack(tf.transform(c[:, 0], c[:, 1])))
    tc3 = T.GEOID.str[2:5].astype(int).values
    cpoly = {c: shapely.union_all(tgeo[tc3 == c]) for c in sorted(set(tc3))}
    ex_ = F.end_x.where(np.isfinite(F.end_x), F.begin_x); ey_ = F.end_y.where(np.isfinite(F.end_y), F.begin_y)
    F["end_x"], F["end_y"] = ex_, ey_
    dcb = np.array([shapely.distance(cpoly[c], shapely.Point(x, y)) if h else np.inf for c, x, y, h in zip(F.county_fips3, F.begin_x, F.begin_y, F.has_coords)])
    dce = np.array([shapely.distance(cpoly[c], shapely.Point(x, y)) if h else np.inf for c, x, y, h in zip(F.county_fips3, F.end_x, F.end_y, F.has_coords)])
    F["coords_ok"] = F.has_coords & (dcb <= COUNTY_TOL_M) & (dce <= COUNTY_TOL_M)
    ok = F.coords_ok.values
    d0, i0 = tree.query(np.column_stack([F.begin_x.fillna(0), F.begin_y.fillna(0)]))
    d1, i1 = tree.query(np.column_stack([F.end_x.fillna(0), F.end_y.fillna(0)]))
    near_d = np.minimum(d0, d1); near_i = np.where(d0 <= d1, i0, i1)
    F["nearest_crossing_id"] = np.where(ok, U.crossing_id.values[near_i], None)
    F["nearest_crossing_km"] = np.where(ok, np.round(near_d / 1000, 3), np.nan)
    within = {}
    for k, (eid, bx, by, ex, ey) in enumerate(zip(F.event_id, F.begin_x, F.begin_y, F.end_x, F.end_y)):
        if not ok[k]: continue
        s = set(tree.query_ball_point([bx, by], RADIUS_M)) | set(tree.query_ball_point([ex, ey], RADIUS_M))
        if s: within[eid] = sorted(s)
    F["crossings_within_1km"] = F.event_id.map(lambda e: len(within.get(e, []))).astype(int)
    F["extent_km"] = np.where(ok, np.round(np.hypot(F.end_x - F.begin_x, F.end_y - F.begin_y) / 1000, 3), np.nan)

    LOC = read("locations", lambda d: d)
    LOC = LOC[LOC.EVENT_ID.astype(int).isin(set(F.event_id[F.candidate & F.coords_ok]))].copy()
    LOC["event_id"] = LOC.EVENT_ID.astype(int)
    LOC["lat"] = pd.to_numeric(LOC.LATITUDE, errors="coerce"); LOC["lon"] = pd.to_numeric(LOC.LONGITUDE, errors="coerce")
    LOC = LOC[LOC.lat.notna() & LOC.lon.notna()]
    lx, ly = tf.transform(LOC.lon.values, LOC.lat.values); LOC["x"] = lx; LOC["y"] = ly
    area = {}
    for eid, g in LOC.groupby("event_id"):
        pts = np.unique(np.round(g[["x", "y"]].values, 1), axis=0)
        if len(pts) >= 3:
            h = shapely.convex_hull(shapely.multipoints(pts))
            if h.geom_type == "Polygon": area[eid] = h

    # careful set and cut-off areas (same objects as core_numbers.py / examples.py)
    G, core, _ = careful_set()
    X = pd.read_parquet("work/edges_plus_strict.parquet"); Cut = pd.read_parquet("work/cuts_plus_strict.parquet")
    Xc = X[X.cut]
    touch = pd.concat([pd.DataFrame(dict(comp=Xc.cu[Xc.su].values, edge=Xc.index[Xc.su].values)),
                       pd.DataFrame(dict(comp=Xc.cv[Xc.sv].values, edge=Xc.index[Xc.sv].values))]).drop_duplicates()
    touch = touch.merge(Cut[["edge", "src", "src_id"]], on="edge")
    touch["crossing_id"] = touch.src + ":" + touch.src_id
    gb = G.set_index("comp")
    careful_comps = set(core.comp)
    def area_info(cid):
        t = touch[touch.crossing_id == cid]
        cc = sorted(c for c in t.comp if c in careful_comps)
        withb = sorted(c for c in t.comp if c in gb.index and gb.loc[c, "bldg"] > 0)
        return dict(careful_set=bool(cc), careful_area_ids="|".join(map(str, cc)),
                    careful_area_buildings=int(sum(gb.loc[c, "bldg"] for c in cc)),
                    careful_area_residents_block=int(round(sum(gb.loc[c, "pop_block"] for c in cc))),
                    careful_area_homes_block=int(round(sum(gb.loc[c, "hu_block"] for c in cc))),
                    careful_area_single_crossing=bool(any(gb.loc[c, "single_crossing"] for c in cc)),
                    cutoff_area_plus_strict=bool(withb), cutoff_area_buildings=int(sum(gb.loc[c, "bldg"] for c in withb)))

    # road-name indexes per county
    route_ix, named_ix, alias_src = {}, {}, {}
    for i, r in U.iterrows():
        for a, srcname in aliases(r.road_eff, r.seg_name, r.seg_refs, r.tier):
            rk = inv_route(a)
            if rk:
                route_ix.setdefault((r.county3, rk), set()).add(i); alias_src.setdefault((i, ("route", rk)), srcname)
            else:
                w = tuple(name_words(a))
                if len(w) >= 2 and not unnamed(a):
                    named_ix.setdefault((r.county3, w), set()).add(i); alias_src.setdefault((i, ("named", w)), srcname)
    named_keys = {}
    for (c, w) in named_ix: named_keys.setdefault(c, set()).add(w)
    route_classes = {}
    for (c, (cls, n)) in route_ix: route_classes.setdefault((c, n), set()).add(cls)
    def inv_stream_base(s):
        """'COTTONWOOD CREEK SOUTH' -> (COTTONWOOD, CREEK); 'HOG CREEK, TRIB' -> (HOG, CREEK): words up to the last stream word before TRIB."""
        if not isinstance(s, str): return ()
        w = stream_words(re.split(r"\bTRIB", s.upper())[0])
        last = max((k for k, x in enumerate(w) if x in STREAM_WORDS), default=None)
        return tuple(w[:last + 1]) if last is not None and last >= 1 else ()
    U["stream_base"] = U.stream.map(inv_stream_base)
    U["stream_trib"] = U.stream.map(lambda s: bool(re.search(r"\bTRIB", str(s).upper())) if isinstance(s, str) else False)
    ORDER = {"same": 4, "spelling variant": 3, "related": 2, "different": 1, "unknown": 0}

    def stream_cmp(i, streams):
        """Narrative streams v crossing i's stream: 'same'; 'spelling variant' (name parts >= STREAM_SIMILAR alike, same
        stream word); 'related' (the inventory lists a tributary or fork of it, or a longer name containing it); 'different';
        'unknown' (no stream on one side)."""
        base = U.stream_base.iat[i]
        if not base or not streams: return "unknown", ""
        best = ("unknown", "")
        for w, raw in streams:
            w = list(w)
            while len(w) > 2 and w[0] in STOP: w = w[1:]
            w = tuple(w)
            if w == base: kind = "related" if U.stream_trib.iat[i] else "same"
            elif w[-1] == base[-1] and SequenceMatcher(None, " ".join(w[:-1]), " ".join(base[:-1])).ratio() >= STREAM_SIMILAR:
                kind = "related" if U.stream_trib.iat[i] else "spelling variant"
            elif len(base) > len(w) and any(base[k:k + len(w)] == w for k in range(len(base) - len(w) + 1)): kind = "related"
            else: kind = "different"
            if ORDER[kind] > ORDER[best[0]]: best = (kind, raw)
        return best

    def dists(j, e):
        if not e.coords_ok: return np.nan, np.nan
        return float(np.hypot(Ux[j] - e.begin_x, Uy[j] - e.begin_y)), float(np.hypot(Ux[j] - e.end_x, Uy[j] - e.end_y))

    rank = lambda h: (h["src"] != "episode", h["incident"], h["quality"] in ("exact", "generic highway resolved"), not h["ref"], h["nroads"] == 1)
    rows, weak = [], {}
    for _, e in F[F.candidate].iterrows():
        c3 = e.county_fips3
        texts = [("event" if e.narrative_source == "event" else "episode (event narrative empty)", e.primary_text)]
        if e.narrative_source == "event" and e.EPISODE_NARRATIVE: texts.append(("episode", e.EPISODE_NARRATIVE))
        hits = {}   # crossing index -> list of name hits
        for src, text in texts:
            sl = sentences(text)
            sst = [extract_streams(s) for _, _, s in sl]
            for si, (_, _, sent) in enumerate(sl):
                incident = bool(INCIDENT.search(sent))
                win = sl if len(sl) <= DEATH_SHORT else sl[max(0, si - 1):si + 3]
                death = any(DEATH.search(s) for _, _, s in win)
                people = any(PEOPLE.search(sl[j][2]) for j in (si - 1, si, si + 1) if 0 <= j < len(sl))
                site = bool(SITE.search(sent)) or bool(sst[si])
                near_streams = [x for j in (si - 1, si, si + 1) if 0 <= j < len(sl) for x in sst[j]]
                found, main_road = [], False
                for kind, key, raw, off, end in extract_roads(sent):
                    before, after = sent[:off], sent[end:]
                    ref = (bool(REFERENCE.search(before)) or bool(re.match(r"(?:Near|From|Toward|Towards|Past|Between)\b", raw))
                           or (bool(OFF_REF.search(before)) and not OFF_MOVE.search(before))
                           or (bool(PAIR_BEFORE.search(before)) and bool(PAIR_AFTER.match(after))))
                    main_road = main_road or not ref
                    if kind == "route":
                        cls, n = key
                        if cls == "HWY":
                            cl = route_classes.get((c3, n), set()) & {"SH", "US", "FMRM"}
                            if not cl: continue
                            quality = "generic highway resolved" if len(cl) == 1 else "generic highway, several route types"
                            idx = set().union(*[route_ix[(c3, (c, n))] for c in cl]); rkey = ("route", ("HWY", n))
                        else:
                            idx = route_ix.get((c3, key), set()); quality = "exact"; rkey = ("route", key)
                    else:
                        k2, quality = best_suffix(list(key), named_keys.get(c3, set()))
                        if not k2: continue
                        idx = named_ix[(c3, k2)]; rkey = ("named", k2)
                    if idx: found.append((rkey, raw, off, ref, quality, frozenset(idx)))
                nroads = len({f[0] for f in found})
                for rkey, raw, off, ref, quality, idx in found:
                    for i in idx:
                        hits.setdefault(i, []).append(dict(src=src, sent=sent, si=si, incident=incident, raw=raw, off=off, ref=ref,
                                                           quality=quality, road_idx=idx, n_on_road=len(idx), nroads=nroads, rkey=rkey,
                                                           death=death, people=people, site=site, sent_streams=sst[si], near_streams=near_streams,
                                                           ref_beside_main=ref and main_road))
        near = set(within.get(e.event_id, []))
        poly = area.get(e.event_id)
        all_streams = extract_streams(e.primary_text)
        crossing_terms = any(e["pr_" + k] for k in KW) or e.fatality_rows_vehicle > 0
        for i in sorted(set(hits) | near):
            u = U.iloc[i]
            db, de = dists(i, e)
            dmin = min(db, de) if e.coords_ok else np.nan
            both = bool(e.coords_ok and db <= RADIUS_M and de <= RADIUS_M)
            inside = bool(poly.covers(shapely.Point(Ux[i], Uy[i]))) if poly is not None else None
            hl = hits.get(i, [])
            h = max(hl, key=rank) if hl else None
            reasons, how, sconf = [], [], ""
            if h is None:
                sa, sraw = stream_cmp(i, all_streams)
                cls = "ambiguous"; method = "coordinates only" + (f" + stream name {sa}" if sa in ("same", "spelling variant", "related") else "")
                grade = ""
                reasons.append("narrative names no road that matches this crossing")
                listed = both and crossing_terms
                why_weak = "coordinates only, event not within 1 km at both points or no crossing/vehicle term"
            else:
                sa, sraw = stream_cmp(i, h["near_streams"])
                ck, craw = stream_cmp(i, h["sent_streams"])
                if h["src"] == "episode": reasons.append("road named only in the episode narrative (covers several events)")
                if not h["incident"]: reasons.append("road named in a sentence without a crossing, vehicle, driver, stall or barricade")
                if h["quality"] not in ("exact", "generic highway resolved"): reasons.append("name match is " + h["quality"])
                pinned = []
                if h["n_on_road"] == 1: pinned.append("only listed crossing on that road in the county")
                if sa == "same" and sum(stream_cmp(j, h["near_streams"])[0] == "same" for j in h["road_idx"]) == 1:
                    pinned.append("stream name agrees")
                if both and sum(all(d <= RADIUS_M for d in dists(j, e)) for j in h["road_idx"]) == 1:
                    pinned.append("both event points within 1 km")
                corroborated = [p for p in pinned if p != "only listed crossing on that road in the county"]
                own = inv_route(u.road_eff) if isinstance(u.road_eff, str) else None   # 'SH 183 (NE 28TH ST)' is a state highway
                long_route = (h["rkey"][0] == "route" and h["rkey"][1][0] in LONG_ROUTES) or (own is not None and own[0] in LONG_ROUTES)
                if not pinned: reasons.append(f"{h['n_on_road']} listed crossings on that road in the county, none singled out")
                elif long_route and not corroborated:
                    reasons.append("numbered state or federal route: its only listed crossing in the county, but no stream or 1 km agreement")
                elif not corroborated and e.coords_ok and dmin > NEAR_M and inside is not True:
                    reasons.append(f"only listed crossing on that road, but {dmin / 1000:.1f} km from the event points and outside the event area")
                if h["ref"]:   # a road written as a reference point is confirmed only when the event is pinned right beside its crossing
                    tight = e.coords_ok and db <= REF_RADIUS_M and de <= REF_RADIUS_M
                    if h["ref_beside_main"]:
                        reasons.append("road written as a reference point beside another named road in the same sentence")
                    elif not (tight or (both and sa == "same")):
                        reasons.append("road written as a reference point ('east of', 'near', 'between', 'at X and Y') and the event is not within 500 m")
                if h["nroads"] > 1 and not corroborated: reasons.append("several matching roads named in the sentence")
                if ck == "different":
                    sconf = craw; reasons.append(f"sentence names another stream ({craw}) than the inventory's ({u.stream})")
                if e.coords_ok and dmin > FAR_M and inside is not True:
                    reasons.append(f"crossing {dmin / 1000:.1f} km from both event points and outside the event area")
                how = list(pinned)
                if i in near and not both: how.append("one event point within 1 km")
                elif both and "both event points within 1 km" not in how: how.append("both event points within 1 km (not unique on road)")
                if sa in ("spelling variant", "related") or (sa == "same" and "stream name agrees" not in how): how.append(f"stream name {sa}")
                cls = "confirmed" if not reasons else "ambiguous"
                method = "road name" + ("; " + "; ".join(how) if how else "")
                grade = ("A" if len(how) >= 2 else "B") if cls == "confirmed" else ""   # A: two or more independent checks
                listed = cls == "confirmed" or (h["src"] != "episode" and h["incident"] and h["quality"] != "partial")
                why_weak = "road named only in the episode narrative, outside an incident sentence, or partially"
                if listed and cls == "ambiguous" and h["n_on_road"] > MAX_CANDIDATES:
                    # a road with many listed crossings: list only the MAX_CANDIDATES nearest to the event, none without coordinates
                    if e.coords_ok:
                        near3 = sorted(h["road_idx"], key=lambda j: (min(dists(j, e)), j))[:MAX_CANDIDATES]
                        listed = i in near3
                        why_weak = f"road with more than {MAX_CANDIDATES} listed crossings: only the {MAX_CANDIDATES} nearest to the event listed"
                    else:
                        listed = False
                        why_weak = f"road with more than {MAX_CANDIDATES} listed crossings and no usable event coordinates"
            if not listed:
                weak[why_weak] = weak.get(why_weak, 0) + 1
                continue
            if h is not None:
                ex = excerpt(h["sent"], h["off"])
            else:
                ss = sentences(e.primary_text)
                pick = next((s for _, _, s in ss if KW["low_water_crossing"].search(s)), None) or \
                       next((s for _, _, s in ss if INCIDENT.search(s)), None) or (ss[0][2] if ss else "")
                ex = excerpt(pick, 0)
            rows.append(dict(
                event_id=e.event_id, episode_id=int(e.EPISODE_ID), event_type=e.EVENT_TYPE, begin=e.begin, county_fips="48%03d" % c3,
                county=e.county, deaths_direct=e.DEATHS_DIRECT, deaths_indirect=e.DEATHS_INDIRECT, injuries_direct=e.INJURIES_DIRECT,
                injuries_indirect=e.INJURIES_INDIRECT, fatality_rows_vehicle=e.fatality_rows_vehicle,
                match_class=cls, grade=grade, method=method, ambiguity_reasons="; ".join(reasons),
                road_in_narrative=h["raw"] if h else "", narrative_source=h["src"] if h else e.narrative_source,
                incident_sentence=h["incident"] if h else None, death_words_near_match=h["death"] if h else None,
                people_involved_near_match=h["people"] if h else None, site_words_in_sentence=h["site"] if h else None,
                name_quality=h["quality"] if h else "", listed_crossings_on_road_in_county=h["n_on_road"] if h else None,
                alias_source=(alias_src.get((i, h["rkey"]), "inventory") if h and h["rkey"][1][0] != "HWY" else ("inventory" if h else "")),
                stream_in_narrative=sraw, stream_agreement=sa, stream_conflict=sconf,
                crossing_id=u.crossing_id, inventory_road=u.road_eff if isinstance(u.road_eff, str) else "",
                inventory_stream=u.stream if isinstance(u.stream, str) else "", lwc_type=u.lwc_type if isinstance(u.lwc_type, str) else "",
                crossing_county=u.county_src if isinstance(u.county_src, str) else "", crossing_county_fips="48%03d" % u.county3,
                crossing_lon=round(float(u.lon), 6), crossing_lat=round(float(u.lat), 6),
                coords_ok=bool(e.coords_ok), d_begin_km=round(db / 1000, 3) if np.isfinite(db) else None,
                d_end_km=round(de / 1000, 3) if np.isfinite(de) else None, within_1km=bool(i in near), both_points_within_1km=both,
                inside_event_area=inside, event_extent_km=e.extent_km if e.coords_ok else None,
                overture_on_30m=bool(u.on_overture_30m), overture_tier=u.tier,
                overture_seg_class=u.seg_cls if isinstance(u.seg_cls, str) else "", overture_seg_name=u.seg_name if isinstance(u.seg_name, str) else "",
                overture_seg_dist_m=round(float(u.seg_dist_m), 1) if pd.notna(u.seg_dist_m) else None,
                overture_flags=(u.seg_flags if isinstance(u.seg_flags, str) else ""),
                overture_label=("no Overture segment attributed" if pd.isna(u.seg_id) else
                                ("ordinary road (no road_flags)" if not (isinstance(u.seg_flags, str) and u.seg_flags) else "flagged " + u.seg_flags)),
                **area_info(u.crossing_id), ncei_url=EVENT_URL.format(e.event_id), excerpt=ex))
    M = pd.DataFrame(rows)
    M["class_order"] = M.match_class.map({"confirmed": 0, "ambiguous": 1})
    M = M.sort_values(["class_order", "begin", "event_id", "crossing_id"]).drop(columns="class_order").reset_index(drop=True)
    F.attrs["weak_links_not_listed"] = dict(sorted(weak.items()))
    return F, M, FAT, U, unmapped_zone, region, area


def lwc_confirmed(lwc, C):
    """The low-water-crossing-mention events that also have a confirmed match to a named inventory crossing."""
    c = C[C.event_id.isin(lwc.event_id)]
    x = c.drop_duplicates("crossing_id")
    return dict(events=int(c.event_id.nunique()), deaths=int(lwc[lwc.event_id.isin(c.event_id)].deaths.sum()),
                crossings=int(x.crossing_id.nunique()),
                crossings_ordinary_road_in_overture=int(x[(x.overture_label == "ordinary road (no road_flags)") & x.overture_on_30m].crossing_id.nunique()),
                crossings_is_bridge_in_overture=int(x[x.overture_flags.fillna("").str.contains("is_bridge")].crossing_id.nunique()),
                crossings_in_careful_set=int(x.careful_set.sum()))


def fatal_block(C, F):
    """Confirmed matches whose event has deaths and whose narrative puts death words near the named road."""
    Cf = C[(C.deaths_direct + C.deaths_indirect > 0) & C.death_words_near_match.astype(bool)]
    ev = F[F.event_id.isin(Cf.event_id)]
    x = Cf.drop_duplicates("crossing_id")
    dead_by = lambda mask: int(F[F.event_id.isin(Cf[mask].event_id)].deaths.sum())
    ordm = (Cf.overture_label == "ordinary road (no road_flags)") & Cf.overture_on_30m
    return dict(definition="confirmed matches in events with deaths whose narrative has death words near the named road (see death_words_near_match_definition)",
                events=int(ev.event_id.nunique()), deaths=int(ev.deaths.sum()), crossings=int(x.crossing_id.nunique()),
                counties=sorted(set(Cf.county)),
                overture_ordinary_road=dict(crossings=int(x[(x.overture_label == "ordinary road (no road_flags)") & x.overture_on_30m].crossing_id.nunique()), deaths=dead_by(ordm)),
                overture_is_bridge=dict(crossings=int(x[x.overture_flags.fillna("").str.contains("is_bridge")].crossing_id.nunique()),
                                        deaths=dead_by(Cf.overture_flags.fillna("").str.contains("is_bridge"))),
                careful_set=dict(crossings=int(x[x.careful_set].crossing_id.nunique()), deaths=dead_by(Cf.careful_set)),
                any_cutoff_area_with_buildings=dict(crossings=int(x[x.cutoff_area_plus_strict].crossing_id.nunique()), deaths=dead_by(Cf.cutoff_area_plus_strict)),
                vehicle_fatality_rows=int(ev.fatality_rows_vehicle.sum()))


def summarise(F, M, FAT, U, unmapped_zone, region, man):
    import numpy as np, pandas as pd
    C = M[M.match_class == "confirmed"]
    A = M[M.match_class == "ambiguous"]
    lwc = F[F.pr_low_water_crossing]
    lwc_any = F[F.kw_low_water_crossing | F.ep_low_water_crossing]
    anyterm = F[F[["pr_" + k for k in KW]].any(axis=1)]
    CE = F[F.event_id.isin(C.event_id)]
    cx = C.drop_duplicates("crossing_id")
    ordinary = cx[(cx.overture_label == "ordinary road (no road_flags)") & cx.overture_on_30m]
    fr = FAT
    def share(d):
        n = len(d); v = int((d.FATALITY_LOCATION == VEHICLE_LOC).sum())
        return dict(fatality_rows=n, vehicle_rows=v, vehicle_share_pct=round(100 * v / n, 1) if n else None)
    fr = fr.merge(F[["event_id", "YEAR", "county"]], on="event_id")
    fr["YEAR"] = fr.YEAR.astype(int)
    loc_counts = fr.FATALITY_LOCATION.value_counts().to_dict()
    # per county
    g = F.groupby(["county_fips3", "county"])
    pc = pd.DataFrame(dict(
        events=g.size(), flash_flood=g.apply(lambda d: int((d.EVENT_TYPE == "Flash Flood").sum())), flood=g.apply(lambda d: int((d.EVENT_TYPE == "Flood").sum())),
        deaths_direct=g.DEATHS_DIRECT.sum(), deaths_indirect=g.DEATHS_INDIRECT.sum(), injuries_direct=g.INJURIES_DIRECT.sum(),
        injuries_indirect=g.INJURIES_INDIRECT.sum(), fatality_rows=g.fatality_rows.sum(), fatality_rows_vehicle=g.fatality_rows_vehicle.sum(),
        lwc_events=g.pr_low_water_crossing.sum(), lwc_event_deaths=g.apply(lambda d: int(d.deaths[d.pr_low_water_crossing].sum())))).reset_index()
    pc["deaths"] = pc.deaths_direct + pc.deaths_indirect; pc["injuries"] = pc.injuries_direct + pc.injuries_indirect
    cc = C.assign(county_fips3=C.county_fips.str[2:].astype(int)).groupby("county_fips3")
    pc = pc.merge(pd.DataFrame(dict(confirmed_match_events=cc.event_id.nunique(), confirmed_match_crossings=cc.crossing_id.nunique())).reset_index(),
                  on="county_fips3", how="left")
    allc = pd.DataFrame(dict(county_fips3=region))
    pc = allc.merge(pc, on="county_fips3", how="left")
    pc["county"] = pc.county.fillna("(no flood event)")
    pc = pc.fillna(0)
    for c in pc.columns:
        if c not in ("county",): pc[c] = pc[c].astype(int)
    pc = pc.sort_values(["deaths", "events", "county_fips3"], ascending=[False, False, True])
    per_county = [dict(county_fips="48%03d" % r.county_fips3, **{k: (r[k] if k == "county" else int(r[k])) for k in pc.columns if k != "county_fips3"}) for _, r in pc.iterrows()]
    lwc_xy = lwc[lwc.coords_ok]
    S = dict(
        generated_by="ncei_events.py", period=f"{FIRST_YEAR}-{LAST_YEAR}", event_types=list(EVENT_TYPES),
        region=dict(definition="Texas counties holding the challenge's south-central-tx census tracts (tract GEOID characters 3 to 5)",
                    counties=len(region), counties_with_flood_events=int(F.county_fips3.nunique())),
        zone_coded_events_mapped=int((F.CZ_TYPE == "Z").sum()),
        zone_coded_texas_flood_events_not_mapped_to_a_county=int(len(unmapped_zone)),
        totals=dict(events=int(len(F)), flash_flood=int((F.EVENT_TYPE == "Flash Flood").sum()), flood=int((F.EVENT_TYPE == "Flood").sum()),
                    deaths_direct=int(F.DEATHS_DIRECT.sum()), deaths_indirect=int(F.DEATHS_INDIRECT.sum()), deaths=int(F.deaths.sum()),
                    injuries_direct=int(F.INJURIES_DIRECT.sum()), injuries_indirect=int(F.INJURIES_INDIRECT.sum()), injuries=int(F.injuries.sum()),
                    fatal_events=int((F.deaths > 0).sum()), fatality_file_rows=int(len(FAT)),
                    events_with_coordinates=int(F.has_coords.sum()), events_with_usable_coordinates=int(F.coords_ok.sum()),
                    usable_coordinates_definition=f"begin and end points within {COUNTY_TOL_M / 1000:.0f} km of the event's own county (union of its challenge tracts)"),
        low_water_crossing_mentions=dict(
            definition="events whose EVENT_NARRATIVE (or, where that is empty, EPISODE_NARRATIVE) matches /low[ -]*water[ -]*(crossing|xing)s?/i",
            events=int(len(lwc)), fatal_events=int((lwc.deaths > 0).sum()), deaths=int(lwc.deaths.sum()),
            deaths_direct=int(lwc.DEATHS_DIRECT.sum()), deaths_indirect=int(lwc.DEATHS_INDIRECT.sum()),
            injuries=int(lwc.injuries.sum()), vehicle_fatality_rows=int(lwc.fatality_rows_vehicle.sum()),
            with_rescue_stranded_or_trapped_words=int(lwc.pr_rescue_stranded_trapped.sum()),
            with_cut_off_stranded_or_trapped_words=int(lwc.pr_cut_off_stranded_trapped.sum()),
            counties=int(lwc.county_fips3.nunique()),
            by_event_type={k: dict(events=int(len(d)), deaths=int(d.deaths.sum())) for k, d in sorted(lwc.groupby("EVENT_TYPE"))},
            with_confirmed_match=lwc_confirmed(lwc, C),
            with_usable_coordinates=int(len(lwc_xy)), with_listed_crossing_within_1km_of_begin_or_end=int((lwc_xy.crossings_within_1km > 0).sum()),
            also_counting_episode_narratives=dict(definition="event OR episode narrative matches (an episode narrative is shared by every event in the episode)",
                                                  events=int(len(lwc_any)), deaths=int(lwc_any.deaths.sum()))),
        any_task_term=dict(definition="EVENT_NARRATIVE (or EPISODE_NARRATIVE where the event narrative is empty) matches any of: " + ", ".join(KW),
                           events=int(len(anyterm)), deaths=int(anyterm.deaths.sum()),
                           per_term_events={k: int(F["pr_" + k].sum()) for k in KW}),
        candidate_events=dict(definition="any task term in the event or episode narrative, or a fatality-file row located Vehicle/Towed Trailer",
                              events=int(F.candidate.sum())),
        matches=dict(
            confirmed_definition=(
                "(1) a road is named in a sentence of the event narrative (or of the episode narrative when the event narrative is "
                "empty) that mentions a crossing, water over the road, a vehicle, a driver, a stall, a barricade or something swept "
                "off the road; (2) the name matches an inventory crossing's road in the same county (CR 628 = County Road 628, "
                "FM = RM = RR, 'Highway N' only when the county lists one route type with that number); (3) the crossing is singled "
                "out: it is the only listed crossing on that road in the county, or it is the only one on that road whose stream "
                "matches a stream named in that sentence or the next or previous one, or it is the only one on that road within "
                "1 km of both event points; (4) nothing contradicts it: a numbered state or federal route needs the stream or the "
                "1 km test, not just being the only listed crossing; with usable coordinates, a crossing singled out only as the "
                "only listed one must lie within 2 km of an event point or inside the event area, and any crossing more than 5 km "
                "from both points and outside the event area fails; a road written as a reference point ('east of', 'near', "
                "'between', 'intersection of', 'at X and Y', 'off X') fails beside another named road and otherwise needs both "
                "event points within 500 m (or 1 km with the stream matching); several matching roads in one sentence need the "
                "stream or 1 km test; a different stream named in the same sentence fails"),
            confirmed_events=int(C.event_id.nunique()), confirmed_pairs=int(len(C)), confirmed_crossings=int(C.crossing_id.nunique()),
            confirmed_event_deaths=int(CE.deaths.sum()), confirmed_fatal_events=int((CE.deaths > 0).sum()),
            confirmed_event_injuries=int(CE.injuries.sum()),
            confirmed_fatal_events_death_words_near_match=int(C[(C.deaths_direct + C.deaths_indirect > 0) & C.death_words_near_match.astype(bool)].event_id.nunique()),
            confirmed_deaths_in_events_with_death_words_near_match=int(F[F.event_id.isin(C[(C.deaths_direct + C.deaths_indirect > 0) & C.death_words_near_match.astype(bool)].event_id)].deaths.sum()),
            death_words_near_match_definition=("drowned, died, death, dead, deceased, killed, fatal, body, perished, succumbed, lost their lives or "
                                               "'neither ... survived' in the narrative when it has at most 6 sentences, else in the sentence "
                                               "naming the road, the one before it or the next two"),
            confirmed_vehicle_fatality_rows=int(CE.fatality_rows_vehicle.sum()),
            confirmed_events_people_involved=int(C[C.people_involved_near_match.astype(bool)].event_id.nunique()),
            confirmed_crossings_people_involved=int(C[C.people_involved_near_match.astype(bool)].crossing_id.nunique()),
            people_involved_definition=("a vehicle, driver or motorist, a person (man, woman, child, occupants, residents...), a rescue, "
                                        "someone stranded, trapped or cut off, or a death in the sentence naming the road or the sentence "
                                        "before or after it"),
            confirmed_by_method={k: int(v) for k, v in C.method.value_counts().sort_index().items()},
            confirmed_by_grade=dict(
                definition=("A: two or more of the checks in the method column (only listed crossing on the road, stream agrees, both "
                            "event points within 1 km, one event point within 1 km, stream related or a spelling variant); B: one check"),
                A_pairs=int((C.grade == "A").sum()), B_pairs=int((C.grade == "B").sum()),
                B_pairs_with_site_words=int(((C.grade == "B") & C.site_words_in_sentence.astype(bool)).sum()),
                site_words_definition=("the sentence naming the road also names a low-water crossing, a crossing, a bridge, a stream, water "
                                       "over the road, or something swept or washed away")),
            confirmed_crossings_overture=dict(
                ordinary_road_within_30m=int(len(ordinary)),
                definition_ordinary="an Overture segment within 30 m carries the crossing and has no road_flags (not is_bridge, not is_tunnel, ...)",
                by_label={k: int(v) for k, v in cx.overture_label.value_counts().sort_index().items()},
                segment_within_30m=int(cx.overture_on_30m.sum())),
            fatal_at_named_crossing=fatal_block(C, F),
            confirmed_crossings_in_careful_set=int(cx.careful_set.sum()),
            confirmed_crossings_bordering_any_cutoff_area_with_buildings=int(cx.cutoff_area_plus_strict.sum()),
            ambiguous_definition=("listed for review: a road named in an incident sentence of the event narrative that fails a confirmed test, "
                                  "or a crossing within 1 km of both event points of an event whose narrative uses a task term "
                                  "(or has a vehicle fatality) but names no matching road"),
            weak_links_not_listed=F.attrs.get("weak_links_not_listed", {}),
            ambiguous_pairs=int(len(A)), ambiguous_events=int(A.event_id.nunique()),
            ambiguous_events_not_confirmed=int(len(set(A.event_id) - set(C.event_id))),
            ambiguous_by_method={k: int(v) for k, v in A.method.str.split(";").str[0].value_counts().sort_index().items()}),
        vehicle_share=dict(
            definition="fatality-file rows located 'Vehicle/Towed Trailer' / all fatality-file rows, for the region's Flash Flood and Flood events",
            all_years=share(fr), years_1996_2019=share(fr[fr.YEAR <= 2019]), years_1996_2024=share(fr[fr.YEAR <= 2024]),
            year_2025_only=share(fr[fr.YEAR == 2025]),
            direct_only=share(fr[fr.FATALITY_TYPE == "D"]), by_location={k: int(v) for k, v in sorted(loc_counts.items(), key=lambda kv: (-kv[1], kv[0]))},
            event_death_count_vs_fatality_rows=dict(event_deaths=int(F.deaths.sum()), fatality_rows=int(len(FAT))),
            comparison="Han and Sharif (2020), Water 12(10) 2884: vehicle-related deaths were 58% of Texas flood deaths, 1959-2019 (statewide, their own compilation)"),
        per_county=per_county,
        sources=dict(ncei_manifest=os.path.relpath(MANIFEST, HERE), ncei_directory_listing=man["directory_listing"],
                     ncei_files=[dict(file=f["file"], url=f["url"], retrieved_utc=f["retrieved_utc"], sha256=f["sha256"]) for f in man["files"]],
                     local_inputs={p: sha256(os.path.join(HERE, p)) for p in ["work/lwc_unique.parquet", "work/lwc_all.parquet",
                                   "work/groups_b_plus_strict.parquet", "work/tiger_check_plus_strict.parquet", "work/tiger_check_plus_strict_multi.parquet",
                                   "work/bldg_plus_strict.parquet", "work/cuts_plus_strict.parquet", "work/edges_plus_strict.parquet"]}))
    return S


def person_names(text):
    """Personal names in one report, found by their context (PERSON)."""
    return {m.group(1) for rx in PERSON for m in rx.finditer(text)}


def screen_names(M, F):
    """The match table as shipped: every personal name found in an event's event or episode narrative, or in the excerpt
    itself, is replaced in that event's excerpts by NAME_REMOVED (the full name and each of its words of three letters or
    more). Returns the table, how many of the reports behind it name a person, and how many excerpts changed."""
    narratives = dict(zip(F.event_id, F.EVENT_NARRATIVE + " " + F.EPISODE_NARRATIVE))
    found = {e: person_names(narratives.get(e, "")) for e in sorted(set(M.event_id))}
    excerpts, changed = [], 0
    for eid, ex in zip(M.event_id, M.excerpt):
        words = set()
        for name in found[eid] | person_names(ex):
            words |= {name} | {w for w in name.split() if len(w) >= 3}
        new = ex
        for w in sorted(words, key=len, reverse=True):
            new = re.sub(r"\b" + re.escape(w) + r"\b", NAME_REMOVED, new)
        new = re.sub(re.escape(NAME_REMOVED) + r"(?:\s+" + re.escape(NAME_REMOVED) + r")+", NAME_REMOVED, new)
        changed += new != ex
        excerpts.append(new)
    out = M.copy()
    out["excerpt"] = excerpts
    return out, sum(1 for v in found.values() if v), changed


def main():
    global NCEI_DIR
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--download-only", action="store_true", help="check the NOAA files (downloading any that are missing) and stop")
    ap.add_argument("--refresh", action="store_true", help="the files NCEI serves today instead of the entry's; the numbers may change")
    ap.add_argument("--ncei-dir", metavar="DIR", help="folder holding the NOAA files (default raw/ncei/, or NCEI_DIR)")
    ap.add_argument("--results", metavar="DIR", default=RESULTS, help="where the shipped copies go (default ../results/ncei)")
    args = ap.parse_args()
    if args.ncei_dir:
        NCEI_DIR = arg_path(os.path.expanduser(args.ncei_dir))
    out = arg_path(args.results) if args.results != RESULTS else RESULTS
    man = download(refresh=args.refresh)
    print(len(man["files"]), "NCEI files verified against", os.path.relpath(MANIFEST, HERE), flush=True)
    if args.download_only: return
    import pandas as pd
    F, M, FAT, U, unmapped_zone, region, area = analyse(man)
    cols = ["event_id", "episode_id", "event_type", "begin", "YEAR", "CZ_TYPE", "CZ_FIPS", "CZ_NAME", "county_fips", "county", "WFO",
            "DEATHS_DIRECT", "DEATHS_INDIRECT", "INJURIES_DIRECT", "INJURIES_INDIRECT", "fatality_rows", "fatality_rows_vehicle",
            "fatality_rows_in_water", "BEGIN_LAT", "BEGIN_LON", "END_LAT", "END_LON", "BEGIN_RANGE", "BEGIN_AZIMUTH", "BEGIN_LOCATION", "END_RANGE", "END_AZIMUTH", "END_LOCATION", "coords_ok", "extent_km",
            "nearest_crossing_id", "nearest_crossing_km", "crossings_within_1km", "narrative_source"] + \
           ["kw_" + k for k in list(KW) + list(EXTRA)] + ["ep_" + k for k in list(KW) + list(EXTRA)] + ["candidate", "ncei_url", "source_file"]
    E = F.assign(episode_id=F.EPISODE_ID.astype(int), event_type=F.EVENT_TYPE, county_fips=["48%03d" % c for c in F.county_fips3],
                 ncei_url=[EVENT_URL.format(e) for e in F.event_id])[cols]
    E.to_csv("work/ncei_events_region.csv", index=False, lineterminator="\n")
    M.to_csv("work/ncei_crossing_matches.csv", index=False, lineterminator="\n")
    S = summarise(F, M, FAT, U, unmapped_zone, region, man)
    with open("work/ncei_summary.json", "w") as f:
        json.dump(S, f, indent=1)
    t = S["totals"]; l = S["low_water_crossing_mentions"]; m = S["matches"]; v = S["vehicle_share"]["all_years"]
    print(f"region events {t['events']} (flash flood {t['flash_flood']}, flood {t['flood']}), deaths {t['deaths']}, injuries {t['injuries']}")
    print(f"low-water-crossing events {l['events']}, deaths {l['deaths']}, injuries {l['injuries']}")
    print(f"confirmed: events {m['confirmed_events']}, crossings {m['confirmed_crossings']}, deaths {m['confirmed_event_deaths']}; "
          f"ordinary-road crossings {m['confirmed_crossings_overture']['ordinary_road_within_30m']}; careful set {m['confirmed_crossings_in_careful_set']}")
    print(f"ambiguous: pairs {m['ambiguous_pairs']}, events {m['ambiguous_events']}")
    print(f"vehicle share {v}")
    # the four files this repository ships
    os.makedirs(out, exist_ok=True)
    E.drop(columns=["ncei_url", "source_file"]).to_csv(os.path.join(out, "ncei_events_region.csv"), index=False, lineterminator="\n")
    Ms, named, changed = screen_names(M, F)
    Ms.to_csv(os.path.join(out, "ncei_crossing_matches.csv"), index=False, lineterminator="\n")
    shutil.copyfile("work/ncei_summary.json", os.path.join(out, "ncei_summary.json"))
    shutil.copyfile(MANIFEST, os.path.join(out, "ncei_manifest.json"))
    print(f"wrote {out}: ncei_events_region.csv {len(E):,} rows (without ncei_url and source_file), ncei_crossing_matches.csv "
          f"{len(Ms):,} rows ({named} of the {Ms.event_id.nunique()} reports behind it name a person; {changed} excerpts changed), "
          "ncei_summary.json, ncei_manifest.json")


if __name__ == "__main__":
    main()
