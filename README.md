# Landfill slope stability — Monte Carlo

A probabilistic slope-stability simulator for a lined landfill. It draws thousands of
synthetic slopes, evaluates the infinite-slope factor of safety for each one, and
reports how often the slope fails under three leachate scenarios — baseline, heavy
rainfall, and a mitigation case.

It also carries twelve real waste-slope failures with the rain that actually fell
before each one, measured at the nearest NOAA gauge, so the model's leachate-head
axis can be read against something that happened.

![The control rail, the slope cross-section, and probability of failure for each scenario](docs/overview.jpg)

## Running it

Open `index.html` in any browser. There is no build step, no install, and no
dependencies — the page is a single self-contained file and never touches the network.

```
git clone https://github.com/Aaron-Zhang128/CEE-110-Project.git
cd CEE-110-Project
open index.html          # macOS; use `start` on Windows, `xdg-open` on Linux
```

## The model

Each sample is one realisation of an infinite slope with a leachate head above the liner:

```
σ   = γ·z·cos²β            total normal stress on the slip plane
u   = γ_w·H·cos²β          pore pressure from the leachate head
σ′  = max(σ − u, 0)        effective normal stress
τ_r = c′ + σ′·tan φ′       shear resistance
τ_d = γ·z·sin β·cos β      driving shear stress
FS  = τ_r / τ_d            the slope has failed when FS ≤ 1
```

The probability of failure is the share of samples with FS ≤ 1.

| Variable | Distribution | Default | Notes |
| --- | --- | --- | --- |
| Cohesion `c′` | lognormal | mean 10 kPa, sd 7.2 | stays positive, skews right |
| Friction angle `φ′` | normal | mean 32°, sd 10.9 | clipped to 1–50° |
| Unit weight `γ` | normal | mean 10.5 kN/m³, sd 2.5 | floored at 1 kN/m³ |
| Leachate head `H` | lognormal | 3.0 / 4.5 / 2.5 m | capped at the slab depth `z` |
| Slope angle `β` | fixed | 25° | |
| Depth to slip plane `z` | fixed | 10 m | vertical depth |
| Leachate unit weight `γ_w` | fixed | 9.81 kN/m³ | |
| Daily rainfall | lognormal | mean 2.24 mm/day, sd 7.12 | site sample; drives the rainfall case |

Material properties are drawn **once** and shared by all three scenarios, so the only
thing separating them is how much leachate sits above the liner — the comparison is a
controlled one, run on the same thousands of slopes wetter or drier.

The random stream is seeded (default 42), so a given seed and sample count reproduce
exactly.

## What it shows

![Overlaid factor-of-safety distributions with the FS = 1 failure threshold](docs/distribution.jpg)

- **Cross-section** — drawn to the current geometry, with each scenario's mean head.
- **Scenario cards** — probability of failure, mean FS, failed-sample count, and the
  reliability index β = (mean FS − 1) / σ_FS, the margin to failure in standard deviations.
- **Factor of safety** — the three distributions on shared bins, with the FS = 1 threshold.
- **Sensitivity to leachate head** — failure probability as the mean head sweeps from a
  dry liner to a fully saturated slab, with each scenario marked. The curve uses common
  random numbers so it stays smooth; markers use each scenario's own spread, so they land
  near the curve rather than exactly on it.
- **Summary** — mean, median, standard deviation and 5th percentile FS per scenario.

Every input on the left is adjustable, including sample count (1 000–100 000) and seed;
everything recomputes as you drag.

## Site rainfall

The site's daily rainfall is supplied as summary statistics — mean 2.24 mm/day,
median 0.69, sd 7.12, min 0.01, max 35.43 — and fitted as a lognormal from the mean
and standard deviation alone. The fit predicts a median of 0.672 against the observed
0.69, 2.6% out, and it never saw the median. A gamma on the same two moments misses
it by 55×; an exponential is rejected by the coefficient of variation (3.18, not 1).

The page samples that distribution day by day across the antecedent window, converts
the accumulated depth to a leachate head with the same infiltration and porosity
coefficients used for the real failures, and reports the failure probability that
rainfall alone produces. With the defaults, a 30-day window gives a median of about
58 mm and a mean head of 0.20 m — this site's ordinary month barely moves the slope,
and what risk there is lives in the tail.

Two caveats are exposed as controls rather than buried: days are drawn independently,
so real storm clustering is not reproduced and the spread of the window total is a
floor; and if the sample counted rain days only, the wet-day fraction slider scales
the accumulation to match.

## The observed failures

![Antecedent rainfall percentile at twelve documented waste-slope failures](docs/rainfall.jpg)

Three further sections carry real data rather than simulated slopes:

- **What the rain was doing** — twelve documented waste-slope failures, ranked by where
  their antecedent rainfall sat in the nearest gauge's own record for that season.
  Colour marks what the published account blamed, which was assigned before any gauge
  was consulted.
- **Rain before the slide** — the daily hyetograph for the six weeks up to whichever
  failure is selected. Click a row in either section to change it.
- **Observed rainfall through the model** — each event's measured rainfall converted to
  a head rise and pushed through this slope's own failure curve.

The conversion is deliberately crude and fully exposed on the control rail:

```
ΔH = infiltration ratio × rainfall ÷ drainable porosity
```

with the antecedent window adjustable from 3 to 45 days. Defaults are 0.30 and 0.10.
The head is taken as rainfall alone on a dry liner, so the last column isolates what
that rain contributes by itself. This is a water-balance sketch, not a measured leachate
level — no gauge in the dataset measured the head inside the waste.

Every failure whose published account blames rain sits at or above the 57th percentile
for 7-day antecedent rainfall. All four whose accounts blame something else — liner
interface shear at Kettleman Hills, a methane explosion at Ümraniye, leachate
recirculation at Doña Juana, static liquefaction of construction spoil at Hongao — sit
at the 40th or below, three of them at zero. Payatas, the deadliest, is also the
wettest: 588 mm in the preceding week, above the 97th percentile for that gauge.

With eleven gauged events and no control group of landfills that took the same rain and
held, this corroborates the published attributions. It does not establish a threshold,
and the page does not claim one.

Rainfall comes from NOAA GHCN-Daily and Global Summary of the Day, pulled live and
computed rather than transcribed. `data/` holds the case list, the generated rainfall
table, the puller, and a full data dictionary with the caveats that matter — gauge
distance, day-boundary offsets, missing days, and the one site (Koshe, Addis Ababa) with
no usable gauge within 150 km.

```
python3 data/build_antecedent_rainfall.py    # NOAA -> data/antecedent-rainfall.csv
python3 data/embed_cases.py                  # -> back into index.html
```

## Notes

The "Acceptable / Marginal / High / Critical" labels on the scenario cards are a display
convention (≤ 1% / ≤ 5% / ≤ 15% / above), not a code requirement — adjust them to
whatever tolerable-risk threshold applies.

The page follows your system light or dark theme.
