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


# Codes missing from OurAirports, mapped to codes it does know
ALIASES = {
    "QLA": "EGHL",  # Lasham Airfield (easyJet maintenance base)
    "MJV": "LELC",  # Murcia-San Javier; IATA code retired when Corvera opened (2019)
}

PLACEHOLDERS = {"XXX", "XXXX", "ZZZ", "ZZZZ"}  # ICAO/IATA "no code assigned"
CODE_RE = re.compile(r"^[A-Z0-9]{3,4}$")


def load_airports():
    """code -> (lat, lng, name); ICAO idents take priority over IATA/FAA codes,
    which take priority over keyword codes (where closed airports like Tegel
    keep their retired TXL/EDDT identifiers)."""
    by_code = {}
    with open(AIRPORTS_CSV, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    def add(code, r):
        code = code.strip().upper()
        if code and code not in PLACEHOLDERS:
            by_code[code] = (float(r["latitude_deg"]), float(r["longitude_deg"]), r["name"])

    # Lowest priority first so later (higher-priority) writes win
    for r in rows:
        for kw in (r["keywords"] or "").split(","):
            if CODE_RE.match(kw.strip().upper()):
                add(kw, r)
    for field in ("local_code", "gps_code", "iata_code", "icao_code", "ident"):
        for r in rows:
            add(r[field] or "", r)
    return by_code


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
    if not (date_col and dep_col and arr_col):
        sys.exit(f"Could not find date/departure/arrival columns.\n"
                 f"Headers seen: {list(rows[0])}\n"
                 f"Expected something like PILOTLOG_DATE / AF_DEP / AF_ARR.")
    print(f"Using columns: date={date_col!r}, dep={dep_col!r}, arr={arr_col!r}, "
          f"time={repr(time_col) if time_col else '(none, using 12:00)'}")

    airports = load_airports()
    flights, unknown, skipped = [], set(), 0
    for r in rows:
        dep = (r.get(dep_col) or "").strip().upper()
        arr = (r.get(arr_col) or "").strip().upper()
        dep = ALIASES.get(dep, dep)
        arr = ALIASES.get(arr, arr)
        ymd = parse_date(r.get(date_col) or "", mdy=mdy)
        if not dep or not arr or not ymd:
            skipped += 1
            continue
        if dep not in airports or arr not in airports:
            unknown.update(c for c in (dep, arr) if c not in airports)
            skipped += 1
            continue
        h, mnt = parse_time(r.get(time_col) if time_col else "")
        y, mo, d = ymd
        flights.append({
            "time": f"{d:02d}/{mo:02d}/{y:04d}T{h:02d}:{mnt:02d}Z",
            "from": [airports[dep][0], airports[dep][1]],
            "to": [airports[arr][0], airports[arr][1]],
            "from_code": dep,
            "to_code": arr,
        })

    flights.sort(key=lambda f: (f["time"][6:10], f["time"][3:5], f["time"][0:2], f["time"][11:16]))
    out = REPO / "flights.json"
    out.write_text(json.dumps(flights, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(flights)} flights to {out}")
    if skipped:
        print(f"Skipped {skipped} rows (missing data or unknown airports).")
    if unknown:
        print(f"Unknown airport codes: {', '.join(sorted(unknown))}")


if __name__ == "__main__":
    main()
