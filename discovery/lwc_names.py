"""Road-name normalisation shared by the matching scripts (Texas conventions)."""
import re
PREFIX = [
    (r"\bFARM[\s-]*TO[\s-]*MARKET( ROAD)?\b", "FM"), (r"\bF M\b", "FM"), (r"\bFM RD\b", "FM"),
    (r"\bRANCH[\s-]*TO[\s-]*MARKET( ROAD)?\b", "RM"), (r"\bRANCH ROAD\b", "RR"), (r"\bR M\b", "RM"),
    (r"\bSTATE HIGHWAY\b", "SH"), (r"\bSTATE HWY\b", "SH"), (r"\bTEXAS STATE HIGHWAY\b", "SH"), (r"\bTX\b", "SH"), (r"\bSTATE ROUTE\b", "SH"),
    (r"\bCOUNTY ROAD\b", "CR"), (r"\bCOUNTY RD\b", "CR"), (r"\bC R\b", "CR"),
    (r"\bUS HIGHWAY\b", "US"), (r"\bUS HWY\b", "US"), (r"\bU S\b", "US"),
    (r"\bINTERSTATE( HIGHWAY)?\b", "IH"), (r"\bI\s(?=\d)", "IH "), (r"\bPARK ROAD\b", "PR"), (r"\bPRIVATE ROAD\b", "PVT"),
]
SUFFIX = {"ROAD": "RD", "STREET": "ST", "LANE": "LN", "DRIVE": "DR", "AVENUE": "AVE", "TRAIL": "TRL", "COURT": "CT",
          "CIRCLE": "CIR", "BOULEVARD": "BLVD", "PARKWAY": "PKWY", "HIGHWAY": "HWY", "NORTH": "N", "SOUTH": "S", "EAST": "E",
          "WEST": "W", "CROSSING": "XING", "PLACE": "PL", "TERRACE": "TER", "LOOP": "LOOP", "SPUR": "SPUR", "PASS": "PASS",
          "CREEK": "CRK", "MOUNT": "MT", "SAINT": "ST", "FORT": "FT", "BEND": "BND", "HOLLOW": "HOLW", "VALLEY": "VLY"}
UNNAMED = re.compile(r"^(UNNAMED|UNKNOWN|NONE|PRIVATE|DRIVEWAY|N/?A)\b")
def norm(s):
    if s is None: return ""
    s = str(s).upper().replace("&", " AND ")
    s = re.sub(r"[^A-Z0-9 ]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    for p, r in PREFIX: s = re.sub(p, r, s)
    toks = [SUFFIX.get(t, t) for t in s.split()]
    return " ".join(toks)
def route_key(s):
    """('FM', '1431') style key for numbered roads, else None."""
    m = re.search(r"\b(FM|RM|RR|SH|CR|US|IH|PR|LOOP|SPUR|BUS)\s*(\d+[A-Z]?)\b", norm(s))
    return (m.group(1), m.group(2)) if m else None
def unnamed(s):
    if not isinstance(s, str): return True
    return bool(UNNAMED.match(norm(s))) or norm(s) == ""
def same_road(a, b_name, b_refs=""):
    """a: inventory road string; b: Overture primary name and route refs."""
    if unnamed(a): return None
    ka = route_key(a)
    b_name = b_name if isinstance(b_name, str) else ""
    b_refs = b_refs if isinstance(b_refs, str) else ""
    cands = [b_name] + [r for r in b_refs.split("|") if r]
    for b in cands:
        if not b: continue
        kb = route_key(b)
        if ka and kb and ka[1] == kb[1] and (ka[0] == kb[0] or {ka[0], kb[0]} <= {"FM", "RM", "RR"}): return True
        if ka and not kb and b.isdigit() and b == ka[1]: return True
        na, nb = norm(a), norm(b)
        if na and nb:
            ta = set(na.split()) - {"RD", "ST", "LN", "DR", "AVE", "N", "S", "E", "W", "TRL", "HWY"}
            tb = set(nb.split()) - {"RD", "ST", "LN", "DR", "AVE", "N", "S", "E", "W", "TRL", "HWY"}
            if ta and tb and (ta <= tb or tb <= ta): return True
    return False
if __name__ == "__main__":
    import argparse
    argparse.ArgumentParser(description=__doc__ + " Run on its own, it prints a few test matches.").parse_args()
    tests = [("SH 163", "State Highway 163", ""), ("FM 2200", "Farm-to-Market Road 2200", ""), ("CR 410", "County Road 410", ""),
             ("RM 12", "Ranch to Market Road 12", ""), ("2ND ST", "2nd Street", ""), ("HACKBERRY RD", "Hackberry Road", ""),
             ("OLD SAN ANTONIO RD", "Old San Antonio Road", ""), ("FM 1431", "Lakeline Boulevard", "FM 1431"),
             ("CR 123", "County Road 124", ""), ("UNNAMED RD", "Main Street", ""), ("LOW WATER XING RD", "Low Water Crossing Road", "")]
    for a, b, r in tests: print(a, "|", b, "|", r, "->", same_road(a, b, r))
