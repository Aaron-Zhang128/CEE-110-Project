# Landfill slope stability — Monte Carlo

An interactive version of the CEE 110 slope-reliability simulation. Open `index.html`
in any browser; there is no build step, no dependencies, and nothing loads from the
network.

## What it does

Each run draws N synthetic slopes and evaluates the infinite-slope factor of safety
for three leachate scenarios — baseline, heavy rainfall, and a mitigation case:

```
σ   = γ·z·cos²β            total normal stress on the slip plane
u   = γ_w·H·cos²β          pore pressure from the leachate head
σ′  = max(σ − u, 0)        effective normal stress
τ_r = c′ + σ′·tan φ′       shear resistance
τ_d = γ·z·sin β·cos β      driving shear stress
FS  = τ_r / τ_d            failure when FS ≤ 1
```

Cohesion and leachate head are lognormal; friction angle and unit weight are normal,
clipped to 1–50° and to a floor of 1 kN/m³. The head is capped at the slab depth.
Material properties are drawn once and shared by all three scenarios, so the only
difference between them is how much leachate sits above the liner.

## What you can change

| Group | Inputs |
| --- | --- |
| Slope & fill | slope angle β, depth to slip plane z, leachate unit weight γ_w |
| Material properties | mean and standard deviation for cohesion c′, friction angle φ′, unit weight γ |
| Leachate scenarios | mean head and standard deviation for each of the three scenarios |
| Run | sample count (1 000–100 000) and RNG seed |

## What it shows

- A cross-section drawn to the current geometry, with each scenario's mean head.
- Probability of failure per scenario, with mean FS and reliability index β = (mean FS − 1) / σ_FS.
- The factor-of-safety distribution across all three scenarios on shared bins.
- Probability of failure as the mean head sweeps from a dry liner to a saturated slab.
- A summary table with mean, median, standard deviation and 5th percentile FS.

The random stream is seeded, so a given seed and sample count reproduce exactly.
