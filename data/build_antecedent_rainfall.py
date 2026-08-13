#!/usr/bin/env python3
"""Attach observed antecedent rainfall to each landfill slope failure.

Reads landfill-failures.csv and, for every failure, finds the best nearby NOAA
rain gauge that was actually recording on the day the slope moved. It then
computes how much rain fell in the windows ending on that date, and how unusual
that total was for the same gauge at the same time of year.

Nothing here is hand-entered -- every rainfall number is pulled live from NOAA.

Two sources are tried, and the one that wins on distance-and-coverage is kept:

  GHCN-Daily   https://www.ncei.noaa.gov/pub/data/ghcn/daily/
               dense multi-decade daily records, best where it exists
  GSOD         https://www.ncei.noaa.gov/data/global-summary-of-the-day/
               airport synoptic reports, fills in the tropics where GHCN is thin

Usage:  python3 build_antecedent_rainfall.py [--cache DIR]
Writes: antecedent-rainfall.csv, antecedent-rainfall.json
"""

import argparse
import concurrent.futures
import csv
import datetime as dt
import io
import json
import math
import os
import sys
import urllib.error
import urllib.request

GHCN = "https://www.ncei.noaa.gov/pub/data/ghcn/daily"
GSOD = "https://www.ncei.noaa.gov/data/global-summary-of-the-day/access"
ISD = "https://www.ncei.noaa.gov/pub/data/noaa/isd-history.csv"
HERE = os.path.dirname(os.path.abspath(__file__))

WINDOWS = [1, 3, 7, 15, 30, 60, 90]
MAX_DISTANCE_KM = 150
MIN_COVERAGE = 0.5           # of the 30 days before failure
DISTANCE_PENALTY_KM = 300    # km-equivalent cost of losing all 30-day coverage
SEASON_HALF_WIDTH = 20       # seasonal reference: same date +/- this many days
REFERENCE_COVERAGE = 0.8     # completeness demanded of a reference window
MIN_REFERENCE_SAMPLE = 100   # windows needed before a percentile is reported
HYETOGRAPH_DAYS = 45         # daily series kept for plotting, ending at failure


# ---------------------------------------------------------------- fetching

def fetch(url, path, allow_404=False):
    """Download url to path once; reuse it afterwards. None if absent."""
    if os.path.exists(path):
        return None if os.path.getsize(path) == 0 else path
    os.makedirs(os.path.dirname(path), exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "CEE110-project/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            body = r.read()
    except urllib.error.HTTPError as e:
        if e.code == 404 and allow_404:
            open(path, "wb").close()   # remember the miss
            return None
        raise
    with open(path, "wb") as f:
        f.write(body)
    return path


def haversine(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


# ---------------------------------------------------------------- GHCN-Daily

def ghcn_catalog(cache):
    """[(id, lat, lon, name, first_year, last_year)] for PRCP-reporting stations."""
    spath = fetch(GHCN + "/ghcnd-stations.txt", os.path.join(cache, "ghcnd-stations.txt"))
    meta = {}
    with open(spath, encoding="utf-8", errors="replace") as f:
        for line in f:
            if len(line) >= 72:
                meta[line[0:11]] = (float(line[12:20]), float(line[21:30]), line[41:71].strip())
    ipath = fetch(GHCN + "/ghcnd-inventory.txt", os.path.join(cache, "ghcnd-inventory.txt"))
    out = []
    with open(ipath, encoding="utf-8", errors="replace") as f:
        for line in f:
            if line[31:35] != "PRCP":
                continue
            m = meta.get(line[0:11])
            if m:
                out.append((line[0:11], m[0], m[1], m[2], int(line[36:40]), int(line[41:45])))
    return out


def ghcn_series(station, cache, _year=None):
    """{date: mm} for one GHCN station. QC-flagged values are treated as missing."""
    path = os.path.join(cache, "dly", station + ".dly")
    try:
        got = fetch(GHCN + "/all/%s.dly" % station, path, allow_404=True)
    except Exception as e:
        sys.stderr.write("    ! %s: %s\n" % (station, e))
        return Series()
    if not got:
        return Series()
    series = Series()
    with open(got, encoding="utf-8", errors="replace") as f:
        for line in f:
            if line[17:21] != "PRCP":
                continue
            year, month = int(line[11:15]), int(line[15:17])
            for d in range(31):
                off = 21 + d * 8
                raw = line[off:off + 5]
                if not raw.strip():
                    continue
                value = int(raw)
                if value == -9999 or line[off + 6].strip():
                    continue
                try:
                    series[dt.date(year, month, d + 1)] = value / 10.0  # tenths mm -> mm
                except ValueError:
                    pass
    return series


# ---------------------------------------------------------------- GSOD

def gsod_catalog(cache):
    """[(id, lat, lon, name, first_year, last_year)] from the ISD history file."""
    path = fetch(ISD, os.path.join(cache, "isd-history.csv"))
    out = []
    with open(path, encoding="latin-1") as f:
        for r in csv.DictReader(f):
            try:
                lat, lon = float(r["LAT"]), float(r["LON"])
            except (ValueError, TypeError):
                continue
            if lat == 0 and lon == 0:
                continue
            begin, end = r["BEGIN"], r["END"]
            if len(begin) != 8 or len(end) != 8:
                continue
            out.append((r["USAF"] + r["WBAN"], lat, lon, r["STATION NAME"].strip(),
                        int(begin[:4]), int(end[:4])))
    return out


# GSOD precipitation flags. D/F/G/H accumulate over the full 24 hours; A, B, C
# and E cover only part of the day and therefore undercount it; I means the
# station filed no precipitation report at all, so its 0.00 is not a measured
# zero and is dropped rather than counted as a dry day.
GSOD_FULL_DAY = set("DFGH")
GSOD_PARTIAL_DAY = set("ABCE")


class Series(dict):
    """{date: mm} plus a note of which days were only partly observed."""

    def __init__(self, *a, **kw):
        dict.__init__(self, *a, **kw)
        self.partial = set()

    def absorb(self, other):
        self.update(other)
        self.partial |= getattr(other, "partial", set())
        return self


def _gsod_year(args):
    station, year, cache = args
    series = Series()
    path = os.path.join(cache, "gsod", str(year), station + ".csv")
    try:
        got = fetch("%s/%d/%s.csv" % (GSOD, year, station), path, allow_404=True)
    except Exception:
        return series
    if not got:
        return series
    with open(got, encoding="utf-8", errors="replace") as f:
        for r in csv.DictReader(f):
            raw = (r.get("PRCP") or "").strip()
            if not raw:
                continue
            try:
                inches = float(raw)
            except ValueError:
                continue
            if inches > 99:  # 99.99 is the missing sentinel
                continue
            flag = (r.get("PRCP_ATTRIBUTES") or "").strip().upper()
            if flag not in GSOD_FULL_DAY and flag not in GSOD_PARTIAL_DAY:
                continue
            try:
                day = dt.date.fromisoformat(r["DATE"][:10])
            except ValueError:
                continue
            series[day] = inches * 25.4
            if flag in GSOD_PARTIAL_DAY:
                series.partial.add(day)
    return series


def gsod_probe(station, cache, year):
    """Just the event year and the ones either side -- enough to score a station."""
    series = Series()
    for y in (year - 1, year, year + 1):
        series.absorb(_gsod_year((station, y, cache)))
    return series


def gsod_series(station, cache, year, span=(-40, 20)):
    """{date: mm} across a window of years around the event."""
    years = range(max(1929, year + span[0]), min(dt.date.today().year, year + span[1]) + 1)
    series = Series()
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        for part in pool.map(_gsod_year, [(station, y, cache) for y in years]):
            series.absorb(part)
    return series


# ---------------------------------------------------------------- analysis

def window_total(series, end, days, min_coverage=MIN_COVERAGE):
    """Rain over the `days` ending on `end` inclusive, and days actually observed."""
    total, seen = 0.0, 0
    for i in range(days):
        day = end - dt.timedelta(days=i)
        if day in series:
            total += series[day]
            seen += 1
    if seen < days * min_coverage:
        return None, seen
    return total, seen


def seasonal_percentile(series, end, days):
    """Rank the event total against same-season totals in the rest of the record.

    Reference sample: every window of the same length ending within
    SEASON_HALF_WIDTH days of the same calendar date, in every other year.
    Returns (percentile, sample size, rough recurrence interval in years).
    """
    event, _ = window_total(series, end, days)
    if event is None:
        return None, 0, None
    target = end.timetuple().tm_yday
    sample = []
    for year in sorted({d.year for d in series}):
        if year == end.year:
            continue
        for shift in range(-SEASON_HALF_WIDTH, SEASON_HALF_WIDTH + 1):
            try:
                day = dt.date(year, 1, 1) + dt.timedelta(days=target - 1 + shift)
            except (ValueError, OverflowError):
                continue
            if day.year != year:
                continue
            total, _ = window_total(series, day, days, min_coverage=REFERENCE_COVERAGE)
            if total is not None:
                sample.append(total)
    if len(sample) < MIN_REFERENCE_SAMPLE:
        return None, len(sample), None
    below = sum(1 for v in sample if v < event)
    pct = 100.0 * below / len(sample)
    exceed = max(1, len(sample) - below) / float(len(sample))
    windows_per_year = (2 * SEASON_HALF_WIDTH + 1) / float(days)
    return pct, len(sample), 1.0 / (exceed * windows_per_year)


def candidates(event, catalog, limit, strict_years):
    """Nearest stations, closest first.

    The ISD history file's begin/end dates are unreliable -- gauges that it
    claims closed years earlier still have data on the server -- so for GSOD we
    ignore them and let the cheap single-year probe decide instead.
    """
    year = event["date"].year
    out = []
    for sid, lat, lon, name, first, last in catalog:
        if strict_years and not (first <= year <= last):
            continue
        d = haversine(event["lat"], event["lon"], lat, lon)
        if d <= MAX_DISTANCE_KM:
            out.append((d, sid, lat, lon, name))
    out.sort()
    return out[:limit]


def evaluate(event, catalog, probe, expand, source, cache, limit, strict_years):
    """Best (score, station, series) this source can offer for one failure.

    `probe` returns just enough record to score the station; only the winner
    pays for `expand`, which pulls the decades needed for the percentile.
    """
    best = None
    for dist, sid, lat, lon, name in candidates(event, catalog, limit, strict_years):
        series = probe(sid, cache, event["date"].year)
        if not series:
            continue
        _, seen = window_total(series, event["date"], 30, min_coverage=0.0)
        coverage = seen / 30.0
        if coverage < MIN_COVERAGE:
            sys.stderr.write("    - %s %s (%.0f km): %d/30 days\n" % (source, sid, dist, seen))
            continue
        score = dist + DISTANCE_PENALTY_KM * (1 - coverage)
        sys.stderr.write("    . %s %s (%.0f km): %d/30 days, score %.0f\n"
                         % (source, sid, dist, seen, score))
        if best is None or score < best[0]:
            best = (score, {"source": source, "id": sid, "name": name, "lat": lat,
                            "lon": lon, "distance_km": dist}, expand)
    return best


# ---------------------------------------------------------------- driver

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", default=os.path.join(HERE, ".ghcn-cache"))
    args = ap.parse_args()

    with open(os.path.join(HERE, "landfill-failures.csv"), encoding="utf-8") as f:
        events = list(csv.DictReader(f))
    for e in events:
        e["lat"], e["lon"] = float(e["lat"]), float(e["lon"])
        e["date"] = dt.datetime.strptime(e["failure_date"], "%Y-%m-%d").date()

    sys.stderr.write("loading station catalogs\n")
    ghcn, gsod = ghcn_catalog(args.cache), gsod_catalog(args.cache)
    sys.stderr.write("  GHCN-Daily %d precipitation stations\n" % len(ghcn))
    sys.stderr.write("  GSOD       %d stations\n" % len(gsod))

    rows = []
    for e in events:
        sys.stderr.write("\n%s -- %s\n" % (e["site"], e["failure_date"]))
        picks = [p for p in (
            evaluate(e, ghcn, ghcn_series, ghcn_series, "GHCN-D", args.cache, 6, True),
            evaluate(e, gsod, gsod_probe, gsod_series, "GSOD", args.cache, 6, False)) if p]
        row = {k: e[k] for k in ("id", "site", "city", "country", "failure_date",
                                 "deaths", "rainfall_implicated", "reported_trigger")}
        if not picks:
            sys.stderr.write("  -> no usable gauge within %d km\n" % MAX_DISTANCE_KM)
            row["station_id"] = ""
            rows.append(row)
            continue

        _, station, expand = min(picks, key=lambda p: p[0])
        sys.stderr.write("  -> %s %s %s (%.0f km)\n"
                         % (station["source"], station["id"], station["name"],
                            station["distance_km"]))
        series = expand(station["id"], args.cache, e["date"].year)
        row.update({
            "source": station["source"], "station_id": station["id"],
            "station_name": station["name"],
            "station_lat": round(station["lat"], 4), "station_lon": round(station["lon"], 4),
            "distance_km": round(station["distance_km"], 1),
            "record_start": min(series).isoformat(), "record_end": max(series).isoformat(),
        })
        for w in WINDOWS:
            total, seen = window_total(series, e["date"], w)
            row["p%d_mm" % w] = None if total is None else round(total, 1)
            row["p%d_days_observed" % w] = seen
        # A gauge's 24-hour accumulation does not have to end at local midnight,
        # so rain that fell before the slide can land on the next calendar day.
        # Shifting the window one day gives the upper bracket on that ambiguity.
        for w in (7, 30):
            total, _ = window_total(series, e["date"] + dt.timedelta(days=1), w)
            row["p%d_mm_shift1" % w] = None if total is None else round(total, 1)
        row["partial_day_reports_30"] = sum(
            1 for i in range(30) if (e["date"] - dt.timedelta(days=i)) in series.partial)
        for w in (7, 30):
            pct, n, period = seasonal_percentile(series, e["date"], w)
            row["p%d_pctl" % w] = None if pct is None else round(pct, 1)
            row["p%d_ref_n" % w] = n
            row["p%d_return_yr" % w] = None if period is None else round(period, 1)
        row["daily_mm"] = [
            (None if (e["date"] - dt.timedelta(days=i)) not in series
             else round(series[e["date"] - dt.timedelta(days=i)], 1))
            for i in range(HYETOGRAPH_DAYS - 1, -1, -1)
        ]
        sys.stderr.write("     7d %s mm (pctl %s)   30d %s mm (pctl %s)\n" % (
            row.get("p7_mm"), row.get("p7_pctl"), row.get("p30_mm"), row.get("p30_pctl")))
        rows.append(row)

    fields = ["id", "site", "city", "country", "failure_date", "deaths",
              "rainfall_implicated", "source", "station_id", "station_name",
              "station_lat", "station_lon", "distance_km", "record_start", "record_end"]
    for w in WINDOWS:
        fields += ["p%d_mm" % w, "p%d_days_observed" % w]
    for w in (7, 30):
        fields += ["p%d_mm_shift1" % w, "p%d_pctl" % w, "p%d_ref_n" % w, "p%d_return_yr" % w]
    fields += ["partial_day_reports_30"]

    with open(os.path.join(HERE, "antecedent-rainfall.csv"), "w", newline="",
              encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    with open(os.path.join(HERE, "antecedent-rainfall.json"), "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=1)
    sys.stderr.write("\nwrote antecedent-rainfall.csv and .json (%d failures)\n" % len(rows))


if __name__ == "__main__":
    main()
