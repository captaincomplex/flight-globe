#!/usr/bin/env python3
"""Convert a CrewLounge PILOTLOG export to the flights.json used by the globes.

Usage:
    python3 tools/pilotlog_to_flights.py MyLogbook.csv
    python3 tools/pilotlog_to_flights.py MyLogbook.csv --mdy   # if your dates are month-first

Export from CrewLounge PILOTLOG:
  - Desktop app: Query page -> leave fields empty -> Search -> CSV (or Excel) button
  - Web: my.crewlounge.center -> Apps / PilotLog -> Export Database

Accepts .csv/.txt (comma, semicolon, or tab delimited) and .xlsx (needs openpyxl).
Airport ICAO/IATA/FAA codes are resolved to coordinates via tools/airports.csv
(OurAirports data, public domain). Writes flights.json in the repo root, sorted
by date, replacing whatever was there.
"""
import csv
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
AIRPORTS_CSV = Path(__file__).resolve().parent / "airports.csv"

# Header candidates, tried in order. PILOTLOG's own field names first,
# then generic fallbacks so other logbook exports work too.
DATE_HEADERS = ["pilotlog_date", "date"]
DEP_HEADERS = ["af_dep", "dep", "departure", "from", "origin"]
ARR_HEADERS = ["af_arr", "arr", "arrival", "to", "destination", "dest"]
DEP_TIME_HEADERS = ["time_dep", "dep_time", "std", "atd", "out", "off_block", "block_off"]
SIM_HEADERS = ["ac_issim", "is_sim", "issim", "simulator", "sim"]
TOTAL_HEADERS = ["time_total", "total_time", "block_time", "block", "duration"]
TRUTHY = {"true", "1", "yes", "y", "x"}


# Codes missing from OurAirports, mapped to codes it does know
ALIASES = {
    "QLA": "EGHL",  # Lasham Airfield (easyJet maintenance base)
    "MJV": "LELC",  # Murcia-San Javier; IATA code retired when Corvera opened (2019)
}

PLACEHOLDERS = {"XXX", "XXXX", "ZZZ", "ZZZZ"}  # ICAO/IATA "no code assigned"
CODE_RE = re.compile(r"^[A-Z0-9]{3,4}$")


def load_airports():
    """Return a lookup(code) function.

    Codes are resolved by kind, not by a single flat map: 4-letter codes hit the
    ICAO tier first, 3-letter codes the IATA tier first, and only then the FAA
    local/GPS identifiers and the keyword codes of closed airports. This matters:
    a flat map lets some US airstrip whose FAA identifier happens to be "NCL"
    shadow Newcastle's IATA code."""
    icao, iata, local, kw = {}, {}, {}, {}
    with open(AIRPORTS_CSV, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    def add(tier, code, r):
        code = code.strip().upper()
        if code and code not in PLACEHOLDERS:
            tier[code] = (float(r["latitude_deg"]), float(r["longitude_deg"]), r["name"])

    for r in rows:
        for k in (r["keywords"] or "").split(","):
            if CODE_RE.match(k.strip().upper()):
                add(kw, k, r)
        add(local, r["local_code"] or "", r)
        add(local, r["gps_code"] or "", r)
        ident = (r["ident"] or "").strip().upper()
        if len(ident) == 4 and ident.isalpha():
            add(icao, ident, r)   # standard ICAO ident
        else:
            add(local, ident, r)  # FAA LIDs and country-prefixed pseudo-idents
        add(icao, r["icao_code"] or "", r)
        add(iata, r["iata_code"] or "", r)

    def lookup(code):
        tiers = (icao, iata, local, kw) if len(code) == 4 else (iata, local, kw)
        for tier in tiers:
            if code in tier:
                return tier[code]
        return None

    return lookup


def read_rows(path):
    if path.suffix.lower() == ".xls":  # legacy Excel 97-2003 (PILOTLOG's Excel export)
        try:
            import xlrd
        except ImportError:
            sys.exit("Reading .xls needs xlrd (pip3 install --user xlrd) — "
                     "or export as CSV from PILOTLOG instead.")
        book = xlrd.open_workbook(path)
        sheet = book.sheet_by_index(0)

        def cell(c):
            if c.ctype == xlrd.XL_CELL_DATE:
                y, mo, d, h, mnt, _ = xlrd.xldate_as_tuple(c.value, book.datemode)
                return f"{y:04d}-{mo:02d}-{d:02d} {h:02d}:{mnt:02d}" if (y, mo, d) != (0, 0, 0) \
                    else f"{h:02d}:{mnt:02d}"
            if c.ctype == xlrd.XL_CELL_NUMBER and c.value == int(c.value):
                return str(int(c.value))
            return str(c.value).strip()
        headers = [cell(c) for c in sheet.row(0)]
        return [dict(zip(headers, (cell(c) for c in sheet.row(r))))
                for r in range(1, sheet.nrows)]
    if path.suffix.lower() == ".xlsx":
        try:
            import openpyxl
        except ImportError:
            sys.exit("Reading .xlsx needs openpyxl (pip3 install --user openpyxl) — "
                     "or export as CSV from PILOTLOG instead.")
        ws = openpyxl.load_workbook(path, read_only=True).active
        it = ws.iter_rows(values_only=True)
        headers = [str(h or "").strip() for h in next(it)]
        return [dict(zip(headers, (str(v or "").strip() for v in row))) for row in it]
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    return list(csv.DictReader(text.splitlines(), dialect=dialect))


def find_column(row, candidates):
    lookup = {k.strip().lower(): k for k in row}
    for c in candidates:
        if c in lookup:
            return lookup[c]
    # substring match as a last resort
    for c in candidates:
        for k in lookup:
            if c in k:
                return lookup[k]
    return None


def parse_date(s, mdy=False):
    s = s.strip()
    m = re.match(r"^(\d{4})\D?(\d{1,2})\D?(\d{1,2})", s)  # year-first
    if m:
        y, a, b = m.groups()
        return int(y), int(a), int(b)
    m = re.match(r"^(\d{1,2})\D(\d{1,2})\D(\d{2,4})", s)  # day- or month-first
    if m:
        a, b, y = (int(g) for g in m.groups())
        if y < 100:
            y += 2000 if y < 70 else 1900
        if a > 12:            # unambiguous: first number must be the day
            return y, b, a
        if b > 12:            # unambiguous: second number must be the day
            return y, a, b
        return (y, a, b) if mdy else (y, b, a)
    return None


def parse_time(s):
    m = re.match(r"^(\d{1,2})\D?(\d{2})", (s or "").strip())
    if m and int(m.group(1)) < 24 and int(m.group(2)) < 60:
        return int(m.group(1)), int(m.group(2))
    return 12, 0  # placeholder when the export has no departure time


def parse_total(s):
    """Block time -> decimal hours. PILOTLOG accepts h:mm (3:30), decimal
    hours (3.5 or 3,5), or plain minutes (210); its own export uses minutes."""
    s = (s or "").strip()
    if not s:
        return None
    m = re.match(r"^(\d{1,3}):(\d{2})$", s)
    if m:
        return round(int(m.group(1)) + int(m.group(2)) / 60, 2)
    try:
        v = float(s.replace(",", "."))
    except ValueError:
        return None
    return round(v, 2) if "." in s or "," in s else round(v / 60, 2)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    mdy = "--mdy" in sys.argv
    if len(args) != 1:
        sys.exit(__doc__)
    src = Path(args[0])
    if not src.exists():
        sys.exit(f"File not found: {src}")

    rows = read_rows(src)
    if not rows:
        sys.exit("No rows found in the export.")

    date_col = find_column(rows[0], DATE_HEADERS)
    dep_col = find_column(rows[0], DEP_HEADERS)
    arr_col = find_column(rows[0], ARR_HEADERS)
    time_col = find_column(rows[0], DEP_TIME_HEADERS)
    sim_col = find_column(rows[0], SIM_HEADERS)
    total_col = find_column(rows[0], TOTAL_HEADERS)
    if not (date_col and dep_col and arr_col):
        sys.exit(f"Could not find date/departure/arrival columns.\n"
                 f"Headers seen: {list(rows[0])}\n"
                 f"Expected something like PILOTLOG_DATE / AF_DEP / AF_ARR.")
    print(f"Using columns: date={date_col!r}, dep={dep_col!r}, arr={arr_col!r}, "
          f"time={repr(time_col) if time_col else '(none, using 12:00)'}")

    lookup = load_airports()
    flights, unknown, skipped, sims = [], set(), 0, 0
    for r in rows:
        if sim_col and (r.get(sim_col) or "").strip().lower() in TRUTHY:
            sims += 1  # simulator session, not a flight
            continue
        dep = (r.get(dep_col) or "").strip().upper()
        arr = (r.get(arr_col) or "").strip().upper()
        dep = ALIASES.get(dep, dep)
        arr = ALIASES.get(arr, arr)
        ymd = parse_date(r.get(date_col) or "", mdy=mdy)
        if not dep or not arr or not ymd:
            skipped += 1
            continue
        dep_ap, arr_ap = lookup(dep), lookup(arr)
        if not dep_ap or not arr_ap:
            unknown.update(c for c, ap in ((dep, dep_ap), (arr, arr_ap)) if not ap)
            skipped += 1
            continue
        h, mnt = parse_time(r.get(time_col) if time_col else "")
        y, mo, d = ymd
        flight = {
            "time": f"{d:02d}/{mo:02d}/{y:04d}T{h:02d}:{mnt:02d}Z",
            "from": [dep_ap[0], dep_ap[1]],
            "to": [arr_ap[0], arr_ap[1]],
            "from_code": dep,
            "to_code": arr,
        }
        hours = parse_total(r.get(total_col)) if total_col else None
        if hours:
            flight["hours"] = hours
        flights.append(flight)

    flights.sort(key=lambda f: (f["time"][6:10], f["time"][3:5], f["time"][0:2], f["time"][11:16]))
    out = REPO / "flights.json"
    out.write_text(json.dumps(flights, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(flights)} flights to {out}")
    if sims:
        print(f"Excluded {sims} simulator sessions.")
    if skipped:
        print(f"Skipped {skipped} rows (missing data or unknown airports).")
    if unknown:
        print(f"Unknown airport codes: {', '.join(sorted(unknown))}")


if __name__ == "__main__":
    main()
