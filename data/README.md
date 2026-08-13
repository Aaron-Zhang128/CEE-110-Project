# Rainfall and landfill slope failure — the data

Twelve documented waste-slope failures, each paired with the rain that actually
fell before it, measured at the nearest NOAA gauge that was recording that week.

The failure list is compiled from the geotechnical literature. The rainfall is
not — it is pulled live from NOAA and computed here, so it can be re-derived
from scratch and checked against the sources.

```
python3 build_antecedent_rainfall.py   # NOAA -> antecedent-rainfall.csv / .json
python3 embed_cases.py                 # -> splices the result into ../index.html
```

The first run downloads ~150 MB of station catalogues and daily records into
`.ghcn-cache/` and takes a few minutes; later runs read the cache and are quick.
Delete the cache to force a clean re-pull.

## Files

| File | What it is |
| --- | --- |
| `landfill-failures.csv` | The case list. Hand-compiled, one row per failure, every row cited. |
| `antecedent-rainfall.csv` | Generated. Rainfall before each failure, plus the gauge it came from. |
| `antecedent-rainfall.json` | The same, plus `daily_mm` — the 45-day daily series the page plots. |
| `build_antecedent_rainfall.py` | Finds the gauge, pulls the record, computes the totals and ranks. |
| `embed_cases.py` | Writes the joined data into `index.html`, which is offline-only. |

## Where the rainfall comes from

Two NOAA products, tried in that order, with whichever wins on distance and
coverage actually being used:

- **GHCN-Daily** — `ncei.noaa.gov/pub/data/ghcn/daily/`. Quality-controlled
  daily totals in tenths of a millimetre, decades deep. Values carrying a
  QC failure flag are dropped.
- **GSOD** — `ncei.noaa.gov/data/global-summary-of-the-day/`. Daily totals in
  inches derived from airport synoptic reports. Thinner, but it covers tropical
  sites where GHCN-Daily has no gauge at all — Bandung, Maputo, Delhi.

Each candidate gauge is scored `distance_km + 300 × (1 − coverage)`, where
coverage is the share of the 30 days before the failure it actually reported.
A close gauge with gaps therefore beats a distant complete one, and nothing
beyond 150 km is used at all.

## Column reference — `antecedent-rainfall.csv`

| Column | Meaning |
| --- | --- |
| `p1_mm` … `p90_mm` | Rain in the 1, 3, 7, 15, 30, 60, 90 days **ending on the failure date**, inclusive. Blank when under half the days were reported. |
| `pN_days_observed` | How many of those N days the gauge actually reported. Read this before trusting the total. |
| `pN_mm_shift1` | The same window moved one day later — see the caveat on day boundaries below. |
| `pN_pctl` | Where that total ranks among the same gauge's totals for the same window length at the same time of year, across every other year on record. 97 = wetter than 97% of comparable windows. |
| `pN_ref_n` | Size of that reference sample. Blank percentile means fewer than 100 comparable windows existed. |
| `pN_return_yr` | Rough recurrence interval implied by the rank, in years. Order-of-magnitude only. |
| `partial_day_reports_30` | Days in the 30-day window whose total covered only part of the day, and so undercounts it. |
| `distance_km` | Gauge to landfill, great-circle. |

The percentile is the number worth reading. A raw total says little — 100 mm in
a week is a drought in Colombo and a deluge in Kettleman City. The percentile
compares each site against itself, in the same season.

## Caveats, in the order they matter

**A gauge is not the landfill.** Distances run from 3 km (Maputo) to 27 km
(Hongao). Convective tropical rain varies sharply over those distances, so
treat individual totals as indicative, not measured-at-site.

**Daily totals do not align with local calendar days.** A gauge's 24-hour
accumulation ends at a fixed hour that is not local midnight, so rain that fell
before a slide can be logged the following day. The clearest case is Xiaping:
the gauge records 131 mm on 8 June 2008 — the well-documented 7 June Hong Kong
rainstorm — while 7 June itself carries no report. The `_shift1` columns give
the upper bracket on this, and Xiaping's 7-day total moves from 71 mm to 200 mm
under it. Neither number is wrong; the ambiguity is real and is shown rather
than resolved.

**GSOD partial-day flags undercount.** Flags D/F/G/H cover the full 24 hours and
are used as-is; A/B/C/E cover 6–18 hours only, are still used, but are counted
in `partial_day_reports_30`. Flag I means the station filed no precipitation
report, so its 0.00 is dropped rather than counted as a dry day — which lowers
reported coverage but never biases a total.

**Missing days lower a total, never raise it.** Leuwigajah's gauge stops on
18 February 2005, three days before the slide, so its window is a floor.

**Koshe has no usable gauge.** Nothing within 150 km of Addis Ababa reported
more than 6 of the 30 days. It is kept in the case list precisely so the gap is
visible instead of quietly dropped.

**The case list is not a complete population.** These are failures documented
well enough to date and locate, which skews toward the deadly and the recent.
Nothing here estimates how often landfills fail — only what the rain was doing
when these ones did.

**Attribution is independent of the rainfall.** The `rainfall_implicated`
column records what the published account blamed, assigned before any gauge was
consulted. That is what makes the comparison worth anything: the rainfall
ranking was never fitted to it.

## What the data shows

Every failure whose published account blames rain sits at the 57th percentile or
above for 7-day antecedent rainfall. All four whose accounts blame something
else — liner-interface shear at Kettleman Hills, a methane explosion at
Ümraniye, leachate recirculation at Doña Juana, static liquefaction of
construction spoil at Hongao — sit at the 40th or below, three of them at zero.
Payatas, the deadliest, is the wettest: 588 mm in the week before it, 905 mm in
the month, both above the 97th percentile of anything that gauge has recorded in
that season.

With eleven gauged events and no control group of landfills that survived the
same rain, this is corroboration, not a dose-response curve. It is enough to say
the published attributions line up with the instrumental record, and not enough
to put a probability on a rainfall threshold.

## Sources

Case histories are cited per row in `landfill-failures.csv`. The main ones:

- Mitchell, Seed & Seed (1990), *Kettleman Hills waste landfill slope failure*, J. Geotech. Engrg. 116(4)
- Kocasoy & Curi (1995), *The Ümraniye-Hekimbaşı open dump accident*, Waste Manage. Res. 13(4)
- Stark, Eid, Evans & Sherry (2000), *Municipal solid waste slope failure*, J. Geotech. Geoenviron. Eng. 126(5)
- Hendron, Fernandez, Prommer, Giroud & Orozco (1999), *Investigation of the Doña Juana slope failure*, Sardinia '99
- Merry, Kavazanjian & Fritz (2005), *Reconnaissance of the July 10, 2000, Payatas landfill failure*, J. Perform. Constr. Facil. 19(2)
- Lavigne et al. (2014), *The 21 February 2005 catastrophic waste avalanche at Leuwigajah dumpsite*, Geoenvironmental Disasters 1:10
- Zhan et al. (2016), *Back-analyses of landfill instability induced by high water level: Shenzhen landfill*
- Yin, Li, Xu & Wang (2016), *Mechanism of the December 2015 catastrophic landslide at the Shenzhen landfill*, Engineering 2(2)
- Blight (2008), *Slope failures in municipal solid waste dumps and landfills: a review*, Waste Manage. Res. 26(5)

Rainfall: NOAA National Centers for Environmental Information, GHCN-Daily and
Global Summary of the Day. Both are public domain.
