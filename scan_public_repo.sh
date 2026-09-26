#!/usr/bin/env bash
# Safety scan of this repository before it goes public. Re-run it after every change:
#
#     bash scan_public_repo.sh            scan the folder this script is in
#     bash scan_public_repo.sh DIR        scan another copy
#
# It checks every file git would commit: tracked files plus untracked files that .gitignore does not exclude (the
# folder need not be a git repository yet). Files .gitignore excludes are counted but not read. It prints PASS, or
# every offending file or line with the rule it breaks, and exits 1 on any finding.
#
# Rules: access keys and credential words; Authorization headers; kaggle.json contents; email addresses (allowed
# only on a "Contact:" line of the top-level README.md); local absolute paths; names of other competitions, clients
# and private tools; files over 5 MB; challenge data layers, caches, submission files and binary data formats;
# challenge strata-table columns in a CSV header; em and en dashes in prose and code; the name of an AI tool or model
# in prose and code (the imagery audit's readings are described without one). A line may carry the marker
# "scan: allow" to pass the credential-word rule only, and then only if every such word on it has an empty value.
# This script itself is excluded from the content rules, because it holds the patterns.
set -uo pipefail
ROOT="$(cd "${1:-$(dirname "$0")}" && pwd)"
PY="${PYTHON:-python3}"
command -v "$PY" >/dev/null 2>&1 || PY=python
command -v "$PY" >/dev/null 2>&1 || { echo "scan_public_repo.sh: needs Python 3" >&2; exit 2; }
command -v git >/dev/null 2>&1 || { echo "scan_public_repo.sh: needs git, to read .gitignore" >&2; exit 2; }
LIST="$(mktemp)"; TMPGIT="$(mktemp -d)"
trap 'rm -rf "$LIST" "$TMPGIT"' EXIT
if [ "$(git -C "$ROOT" rev-parse --show-toplevel 2>/dev/null)" = "$ROOT" ]; then
  G=(git -C "$ROOT")
  "${G[@]}" ls-files -co --exclude-standard -z > "$LIST"
else
  git --git-dir="$TMPGIT" init -q
  G=(git --git-dir="$TMPGIT" --work-tree="$ROOT")
  "${G[@]}" ls-files -o --exclude-standard -z > "$LIST"
fi
IGNORED="$("${G[@]}" ls-files -o -i --exclude-standard | wc -l | tr -d ' ')"

"$PY" - "$ROOT" "$LIST" "$IGNORED" <<'PYEOF'
import os, re, sys
root, listfile, ignored = sys.argv[1], sys.argv[2], int(sys.argv[3])
files = sorted(f for f in open(listfile, "rb").read().decode("utf-8", "replace").split("\0") if f)
SELF = "scan_public_repo.sh"
found, notes = [], []

def flag(rule, where, text=""):
    found.append((rule, where, " ".join(text.split())[:160]))

NAME_RULES = [
    ("local configuration or key file", r"(^|/)(\.env(\..*)?|kaggle\.json|id_rsa|id_ed25519|credentials(\.json)?)$|\.(pem|key|p12|pfx)$"),
    ("binary data format that is never committed", r"\.(parquet|pbf|gpkg|shp|shx|dbf|feather|arrow|h5|npy|npz|pkl|pickle|zip|gz|7z|tar)$"),
    ("challenge data layer", r"(census-tracts|strata-tract-table|overture-roads|overture-buildings|overture-pois|microsoft-buildings|census-tiger-roads|hifld-|census-cbp|sample-submission)"),
    ("challenge cache or layer folder", r"(^|/)(cache|reference|strata)/|(^|/)(reference|strata)__"),
    ("submission file", r"(^|/)submission[^/]*\.csv$"),
]
HARD = [
    ("GitHub token", r"\b(ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}|\bgithub_pat_[A-Za-z0-9_]{20,}"),
    ("AWS access key", r"\b(AKIA|ASIA)[0-9A-Z]{16}\b"),
    ("private key block", r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    ("Slack token", r"\bxox[abprs]-[A-Za-z0-9-]{10,}"),
    ("Google API key", r"\bAIza[0-9A-Za-z_\-]{35}\b"),
    ("API key", r"\bsk-[A-Za-z0-9_\-]{20,}"),
    ("Authorization header", r"(?i)\bauthorization\s*[:=]|\bbearer\s+[A-Za-z0-9._\-]{8,}"),
    ("kaggle.json contents", r'"username"\s*:\s*"[^"]*"\s*,\s*"key"\s*:|"key"\s*:\s*"[0-9a-f]{32}"'),
    ("local absolute path", r"/home/[A-Za-z0-9_.\-]+|/Users/[A-Za-z0-9_.\-]+|/root/|/mnt/|/sessions/|/tmp/|/private/var/|/content/drive|"
                            r"/kaggle/|file:///|\b[A-Z]:\\|\\Users\\|Desktop[/\\]|Comptetitions|01_competitions|\bzwork\b"),
    ("other competition, client or private tool", r"(?i)\b(barbados|eswatini|indabax|drought|geo-?ai|waxal|ptcg|yo-?milk|profeeds|origen|"
                                                  r"replit|aicreative|kaggriculture|amini|tanzania|climate[-_ ]?risk|climate[-_ ]?health|"
                                                  r"war-?room|operating_agreement|submissions_log|deepseek|qwen|cowork)\b"),
    ("other competition or client", r"\b(Climate|MIRA)\b"),
]
B0, B1 = r"(?<![A-Za-z0-9])", r"(?![A-Za-z0-9])"            # word edges that treat _ as a separator: API_TOKEN, db_password
WORDS = rf"(?i){B0}(tokens?|api[_-]?keys?|apikey|secrets?|passwords?|passwd){B1}"
FILLED = rf"(?i){B0}(tokens?|api[_-]?keys?|apikey|secrets?|passwords?|passwd|key_id){B1}[\"']?\s*[:=]?\s*(['\"])(?!\2)."
EMAIL = r"[A-Za-z0-9._%+\-]{1,64}@[A-Za-z0-9\-]{1,63}(?:\.[A-Za-z0-9\-]{1,63}){0,8}\.[A-Za-z]{2,24}"   # bounded: no slow backtracking
DASH = "[\u2012\u2013\u2014\u2015]"   # figure dash, en dash, em dash, horizontal bar
MODEL = r"(?i)\b(claude|anthropic|chatgpt|openai|gpt|llms?|vision model|ai model|language model)\b"
PROSE = (".md", ".txt", ".rst", ".py", ".sh", ".ql", ".cfg", ".toml", ".yml", ".yaml", ".ipynb")
STRATA_COLS = (r"\b(svi_[a-z_]+|pop_total|pop_urban|pop_rural|pct_urban|ur_class|cvi_[a-z_]+|ruca_[a-z_]+|rucc_[a-z0-9_]+|"
               r"nchs_[a-z0-9_]+|usdm_[a-z0-9_]+|usfs_[A-Za-z_]+|epht_[a-z_]+|tribal_[a-z_]+)\b")

for f in files:
    p = os.path.join(root, f)
    if not os.path.isfile(p):
        continue
    for rule, pat in NAME_RULES:
        if re.search(pat, f, re.I):
            flag(rule, f)
    for rule, pat in HARD[-3:]:
        if re.search(pat, f):
            flag(rule + " (in the file name)", f)
    size = os.path.getsize(p)
    if size > 5 * 1024 * 1024:
        flag("file over 5 MB (contents not read)", f, f"{size / 1024 / 1024:.1f} MB")
        continue
    if f == SELF:
        continue
    raw = open(p, "rb").read()
    if b"\0" in raw[:8192]:
        notes.append(f"binary file, contents not read: {f}")
        continue
    text = raw.decode("utf-8", "replace")
    prose = f.endswith(PROSE) or os.path.basename(f) in ("LICENSE", ".gitignore")
    for i, line in enumerate(text.splitlines(), 1):
        where = f"{f}:{i}"
        for rule, pat in HARD:
            if re.search(pat, line):
                flag(rule, where, line)
        if re.search(r"(?i)kaggle", line) and not (f == ".gitignore" and line.strip() == "kaggle.json"):
            flag("Kaggle reference", where, line)
        if re.search(WORDS, line):
            if "scan: allow" in line and not re.search(FILLED, line):
                notes.append(f"credential word passed by its 'scan: allow' marker (empty values): {where}")
            else:
                flag("credential word", where, line)
        for m in (re.finditer(EMAIL, line) if "@" in line else ()):
            if not (f == "README.md" and re.match(r"^\s*([-*]\s+)?Contact:", line)):
                flag("email address", where, m.group(0))
        if prose and re.search(DASH, line):
            flag("em or en dash", where, line)
        if prose and re.search(MODEL, line):
            flag("AI tool or model named", where, line)
        if i == 1 and f.endswith(".csv"):
            cols = sorted(set(m.group(0) for m in re.finditer(STRATA_COLS, line)))
            if cols:
                flag("challenge strata-table column in a CSV header", where, ", ".join(cols))

for n in notes:
    print("note:", n)
if found:
    print(f"FAIL: {len(found)} finding(s) in {len(files)} files")
    for rule, where, text in found:
        print(f"  {rule} | {where}" + (f" | {text}" if text else ""))
    sys.exit(1)
print(f"PASS: {len(files)} files scanned; {ignored} files excluded by .gitignore were present and not read")
PYEOF
