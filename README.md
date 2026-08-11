# Landfill slope stability — Monte Carlo

A probabilistic slope-stability simulator for a lined landfill. It draws thousands of
synthetic slopes, evaluates the infinite-slope factor of safety for each one, and
reports how often the slope fails under three leachate scenarios — baseline, heavy
rainfall, and a mitigation case.

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

## Notes

The "Acceptable / Marginal / High / Critical" labels on the scenario cards are a display
convention (≤ 1% / ≤ 5% / ≤ 15% / above), not a code requirement — adjust them to
whatever tolerable-risk threshold applies.

The page follows your system light or dark theme.
