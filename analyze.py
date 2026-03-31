#!/usr/bin/env python3
"""
analyze.py -- Resource extraction and GDP/pc trajectory analysis.

Data sources:
  - Maddison Project Database 2023 (downloaded once, cached)
  - World Bank WDI: indicator NY.GDP.PCAP.PP.KD (constant 2021 PPP $)

Method:
  - T=0 is the first significant extraction year per country (hardcoded).
  - Load GDP/pc from T-20 to T+40 in calendar years.
  - Chain: WB anchored at 1990; Maddison growth rates backfilled pre-1990.
  - Normalize GDP/pc to 100 at T=0.
  - Compute pre-CAGR (T-20 to T=0) and post-CAGR (T=0 to T+30).

Usage:
  python analyze.py            # use cached downloads
  python analyze.py --refresh  # force re-download
"""

import sys
import json
import math
from pathlib import Path

try:
    import requests
    import openpyxl
except ImportError as e:
    sys.exit(
        f"Missing dependency: {e}\n"
        "Install with: pip install requests openpyxl"
    )

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SCRIPT_DIR   = Path(__file__).parent
CACHE_DIR    = SCRIPT_DIR / "cache"
MADDISON_URL = "https://dataverse.nl/api/access/datafile/421302"
WB_BASE      = (
    "https://api.worldbank.org/v2/country/{iso}/indicator"
    "/NY.GDP.PCAP.PP.KD?format=json&per_page=1000&date=1800:2024"
)

PRE_WINDOW  = 20   # CAGR: T-20 to T=0
POST_WINDOW = 30   # CAGR: T=0  to T+30
EVT_START   = -20  # earliest event-time year to load
EVT_END     = +40  # latest  event-time year to load
MAX_GAP     = 5    # max consecutive missing years before skipping a country

# Rows for these countries get a ">>>" prefix in output
SPOTLIGHT = {"Norway", "Nigeria", "Equatorial Guinea"}

# (display name, WB ISO-3, T=0 year, resource type)
COUNTRIES = [
    ("Angola",            "AGO", 1975, "oil"),
    ("Botswana",          "BWA", 1971, "diamonds"),
    ("Chad",              "TCD", 2003, "oil"),
    ("Equatorial Guinea", "GNQ", 1996, "oil"),
    ("Ghana",             "GHA", 2010, "oil"),
    ("Indonesia",         "IDN", 1885, "oil"),
    ("Kazakhstan",        "KAZ", 1991, "oil"),
    ("Malaysia",          "MYS", 1910, "oil"),
    ("Mexico",            "MEX", 1901, "oil"),
    ("Nigeria",           "NGA", 1958, "oil"),
    ("Norway",            "NOR", 1971, "oil"),
    ("Saudi Arabia",      "SAU", 1938, "oil"),
    ("UAE",               "ARE", 1962, "oil"),
    ("Venezuela",         "VEN", 1920, "oil"),
]

# ---------------------------------------------------------------------------
# Download helpers
# ---------------------------------------------------------------------------

def ensure_cache():
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


def download_maddison(refresh=False):
    """Download Maddison 2023 Excel and cache it. Returns local Path."""
    path = CACHE_DIR / "maddison.xlsx"
    if path.exists() and not refresh:
        print(f"  [cache] Maddison: {path}")
        return path
    print("  Downloading Maddison Project Database 2023 (approx 5 MB)...", flush=True)
    try:
        r = requests.get(MADDISON_URL, timeout=180, stream=True)
        r.raise_for_status()
    except Exception as e:
        print(
            f"\n  ERROR: Could not download Maddison data: {e}\n"
            f"\n  Manual fix: download the file yourself and place it at:\n"
            f"    {path}\n"
            f"\n  Download page:\n"
            f"    https://www.rug.nl/ggdc/historicaldevelopment/maddison/releases/maddison-project-database-2023\n"
            f"  Direct URL:\n"
            f"    {MADDISON_URL}\n"
        )
        return None
    with open(path, "wb") as f:
        for chunk in r.iter_content(chunk_size=65536):
            f.write(chunk)
    print(f"  Saved: {path}")
    return path


def download_wb(iso3, refresh=False):
    """Download WB GDP/pc series for one country and cache as JSON."""
    path = CACHE_DIR / f"{iso3}_gdp.json"
    if path.exists() and not refresh:
        return
    url = WB_BASE.format(iso=iso3)
    all_rows = []
    page = 1
    while True:
        r = requests.get(f"{url}&page={page}", timeout=30)
        r.raise_for_status()
        body = r.json()
        meta = body[0]
        rows = body[1] if len(body) > 1 and body[1] else []
        all_rows.extend(rows)
        if page >= meta.get("pages", 1):
            break
        page += 1
    with open(path, "w") as f:
        json.dump(all_rows, f)


# ---------------------------------------------------------------------------
# Load helpers
# ---------------------------------------------------------------------------

def load_wb(iso3):
    """Load cached WB JSON -> {year: gdppc}. Returns empty dict if file missing."""
    path = CACHE_DIR / f"{iso3}_gdp.json"
    if not path.exists():
        return {}
    with open(path) as f:
        rows = json.load(f)
    data = {}
    for row in rows:
        val = row.get("value")
        if val is not None:
            try:
                data[int(row["date"])] = float(val)
            except (KeyError, ValueError, TypeError):
                pass
    return data


def load_maddison(path):
    """
    Parse MPD2023 Excel -> {iso3: {year: gdppc}}.

    MPD2023 'Full data' sheet is long-format with columns:
      countrycode, country, year, gdppc, pop, ...
    gdppc is in 2011 international dollars.
    We only use Maddison for growth rates (splice), so the unit difference
    vs WB (2021 PPP $) does not affect results.
    """
    print("  Parsing Maddison Excel (may take a moment)...", flush=True)
    wb_xl = openpyxl.load_workbook(path, read_only=True, data_only=True)

    # Prefer the 'Full data' sheet; fall back to first sheet
    sheet = None
    for name in wb_xl.sheetnames:
        nl = name.lower().strip()
        if "full" in nl or nl in ("data", "gdppc", "gdp pc"):
            sheet = wb_xl[name]
            break
    if sheet is None:
        sheet = wb_xl[wb_xl.sheetnames[0]]

    rows_iter = sheet.iter_rows(values_only=True)
    raw_hdr = next(rows_iter, None)
    if raw_hdr is None:
        wb_xl.close()
        return {}

    headers = [str(h).strip().lower() if h is not None else "" for h in raw_hdr]

    def find_col(*candidates):
        for c in candidates:
            if c in headers:
                return headers.index(c)
        return None

    iso_c  = find_col("countrycode", "iso3", "isocode", "code", "iso")
    year_c = find_col("year")
    gdp_c  = find_col("gdppc", "cgdppc", "rgdpnapc", "gdp_pc", "gdppc_d")

    if None in (iso_c, year_c, gdp_c):
        sample = headers[:12]
        print(f"  WARNING: Cannot detect Maddison columns. Headers sample: {sample}")
        wb_xl.close()
        return {}

    data = {}
    for row in rows_iter:
        try:
            iso  = str(row[iso_c]).strip().upper()
            year = int(float(str(row[year_c])))
            val  = float(row[gdp_c])
        except (TypeError, ValueError, IndexError):
            continue
        if not iso or iso == "NAN":
            continue
        if iso not in data:
            data[iso] = {}
        data[iso][year] = val

    wb_xl.close()
    print(f"  Loaded Maddison data for {len(data)} countries.")
    return data


# ---------------------------------------------------------------------------
# Splicing
# ---------------------------------------------------------------------------

def build_spliced(iso3, t0, mad, wb):
    """
    Growth-rate splice: WB anchored at 1990 (or nearest available year <= 1995).
    Pre-anchor: backfill using Maddison year-on-year growth rates.
    Post-anchor: WB values directly.

    Returns {year: gdppc}, covering t0+EVT_START to t0+EVT_END.
    Years without data are absent from the dict (not None).
    """
    win_start = t0 + EVT_START
    win_end   = t0 + EVT_END

    # Find WB anchor (1990 preferred; walk forward to 1995 if missing)
    anchor_year = None
    for y in range(1990, 1996):
        if y in wb:
            anchor_year = y
            break

    # If no WB anchor near 1990, use the earliest available WB year
    if anchor_year is None and wb:
        anchor_year = min(wb.keys())

    if anchor_year is None:
        return {}

    spliced = {}

    # WB covers anchor year onwards
    for y in range(anchor_year, win_end + 1):
        if y in wb:
            spliced[y] = wb[y]

    # Maddison backfill pre-anchor
    mad_c = mad.get(iso3, {})
    for y in range(anchor_year - 1, win_start - 1, -1):
        nxt = y + 1
        if nxt not in spliced:
            continue  # chain broken; skip
        m_cur = mad_c.get(y)
        m_nxt = mad_c.get(nxt)
        if m_cur and m_nxt and m_cur > 0:
            g = (m_nxt - m_cur) / m_cur
            spliced[y] = spliced[nxt] / (1 + g)

    return spliced


def max_consecutive_gap(spliced, start, end):
    """Longest run of consecutive missing years in [start, end]."""
    best = gap = 0
    for y in range(start, end + 1):
        if y not in spliced:
            gap += 1
            best = max(best, gap)
        else:
            gap = 0
    return best


# ---------------------------------------------------------------------------
# CAGR
# ---------------------------------------------------------------------------

def cagr(v0, v1, years):
    """Compound annual growth rate between two values over `years` years."""
    if v0 and v1 and v0 > 0 and v1 > 0 and years > 0:
        return (v1 / v0) ** (1.0 / years) - 1.0
    return None


# ---------------------------------------------------------------------------
# Analysis loop
# ---------------------------------------------------------------------------

def analyze_all(mad):
    """Return list of result dicts for countries that pass data quality."""
    results = []
    for name, iso3, t0, resource in COUNTRIES:
        wb = load_wb(iso3)
        spliced = build_spliced(iso3, t0, mad, wb)

        # Data quality gate: max consecutive gap in CAGR window
        check_start = t0 - PRE_WINDOW
        check_end   = t0 + POST_WINDOW
        gap = max_consecutive_gap(spliced, check_start, check_end)
        if gap > MAX_GAP:
            print(
                f"  SKIP {name}: {gap} consecutive missing years "
                f"in T-{PRE_WINDOW} to T+{POST_WINDOW} window."
            )
            continue

        # Warn if Maddison pre-1960 coverage is sparse
        mad_c = mad.get(iso3, {})
        pre60 = [y for y in range(check_start, min(1960, t0 + 1))]
        if pre60:
            covered = sum(1 for y in pre60 if y in mad_c)
            frac = covered / len(pre60)
            if frac < 0.5:
                print(
                    f"  WARN {name}: sparse Maddison pre-1960 coverage "
                    f"({covered}/{len(pre60)} years, {frac:.0%})."
                )

        gdp_t0   = spliced.get(t0)
        gdp_pre  = spliced.get(t0 - PRE_WINDOW)
        gdp_post = spliced.get(t0 + POST_WINDOW)

        if not gdp_t0:
            print(f"  SKIP {name}: no GDP value at T=0 ({t0}).")
            continue

        norm_t30 = (gdp_post / gdp_t0 * 100.0) if gdp_post else None

        results.append({
            "name":      name,
            "resource":  resource,
            "t0":        t0,
            "pre_cagr":  cagr(gdp_pre,  gdp_t0,   PRE_WINDOW),
            "post_cagr": cagr(gdp_t0,   gdp_post,  POST_WINDOW),
            "gdp_t0":    gdp_t0,
            "norm_t30":  norm_t30,
        })
        print(f"  OK  {name}")

    return results


# ---------------------------------------------------------------------------
# Pretty-printing
# ---------------------------------------------------------------------------

def fmt_pct(v):
    return f"{v * 100:+.2f}%" if v is not None else "N/A"

def fmt_dollar(v):
    return f"${v:,.0f}" if v is not None else "N/A"

def fmt_norm(v):
    return f"{v:.1f}" if v is not None else "N/A"


# Column spec: (header, key, align, min-width)
COLUMNS = [
    ("Country",       "name",      "l", 20),
    ("Resource",      "resource",  "l", 10),
    ("Year",          "t0",        "r",  6),
    ("Pre-CAGR",      "pre_cagr",  "r", 10),
    ("Post-CAGR",     "post_cagr", "r", 10),
    ("GDP at T=0",    "gdp_t0",    "r", 12),
    ("Norm at T+30",  "norm_t30",  "r", 13),
]


def format_row(r):
    """Return list of string cells for one result row."""
    return [
        r["name"],
        r["resource"],
        str(r["t0"]),
        fmt_pct(r["pre_cagr"]),
        fmt_pct(r["post_cagr"]),
        fmt_dollar(r["gdp_t0"]),
        fmt_norm(r["norm_t30"]),
    ]


def print_table(results, title):
    rows = [format_row(r) for r in results]

    # Compute column widths
    widths = [max(len(col[0]), col[3]) for col in COLUMNS]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))

    sep   = "  "
    total = sum(widths) + len(sep) * (len(COLUMNS) - 1) + 4  # 4 for prefix

    print()
    print("=" * total)
    print(f"  {title}")
    print("=" * total)

    # Header
    header_cells = []
    for i, (hdr, _, align, _) in enumerate(COLUMNS):
        if align == "l":
            header_cells.append(hdr.ljust(widths[i]))
        else:
            header_cells.append(hdr.rjust(widths[i]))
    print("    " + sep.join(header_cells))
    print("-" * total)

    # Data rows
    for r, row in zip(results, rows):
        prefix = ">>> " if r["name"] in SPOTLIGHT else "    "
        cells = []
        for i, (_, _, align, _) in enumerate(COLUMNS):
            if align == "l":
                cells.append(row[i].ljust(widths[i]))
            else:
                cells.append(row[i].rjust(widths[i]))
        print(prefix + sep.join(cells))

    print("=" * total)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    refresh = "--refresh" in sys.argv
    ensure_cache()

    # -- Download phase --
    print("\n=== Step 1: Fetching data ===")
    mad_path = download_maddison(refresh)

    failed_wb = []
    for name, iso3, t0, _ in COUNTRIES:
        print(f"  WB [{iso3}] {name}...", end="", flush=True)
        try:
            download_wb(iso3, refresh)
            print(" OK")
        except Exception as e:
            print(f" FAILED ({e})")
            failed_wb.append(name)

    if failed_wb:
        print(f"  WARNING: WB download failed for: {', '.join(failed_wb)}")

    # -- Load Maddison --
    print("\n=== Step 2: Loading data ===")
    mad = {}
    if mad_path is not None:
        try:
            mad = load_maddison(mad_path)
        except Exception as e:
            print(f"  WARNING: Could not parse Maddison Excel: {e}")
            print("  Continuing with World Bank data only (no pre-1990 backfill).")
        if not mad:
            print(
                "  WARNING: Maddison data loaded empty.\n"
                "  The Excel sheet layout may have changed. Check column names.\n"
                "  Continuing with WB-only data."
            )
    else:
        print("  Skipping Maddison load (file not available).")
        print("  Pre-1990 backfill unavailable; countries with T=0 before 1970 will likely be skipped.")

    # -- Analyze --
    print("\n=== Step 3: Analyzing ===")
    results = analyze_all(mad)

    if not results:
        print("\nNo countries passed data quality checks. Nothing to display.")
        return

    # -- Output --
    print()

    # Table 1: alphabetical order (already sorted since COUNTRIES is alpha)
    print_table(results, "Table 1 -- Countries (alphabetical order)")

    # Table 2: sorted by post-CAGR descending
    by_post = sorted(
        results,
        key=lambda r: r["post_cagr"] if r["post_cagr"] is not None else -99.0,
        reverse=True,
    )
    print_table(by_post, "Table 2 -- Countries sorted by post-extraction CAGR (descending)")

    # Summary note
    print()
    print("  Notes:")
    print(f"  Pre-CAGR  = compound annual growth rate from T-{PRE_WINDOW} to T=0")
    print(f"  Post-CAGR = compound annual growth rate from T=0  to T+{POST_WINDOW}")
    print(f"  GDP at T=0 in constant 2021 PPP $ (World Bank NY.GDP.PCAP.PP.KD),")
    print(f"  backfilled pre-1990 using Maddison 2023 growth rates.")
    print(f"  Norm at T+30 = GDP/pc indexed to 100 at T=0, value at T+{POST_WINDOW}.")
    print(f"  >>> marks spotlight countries (Norway, Nigeria, Equatorial Guinea).")
    print()


if __name__ == "__main__":
    main()
