#!/usr/bin/env python3
"""Render the project's rainfall figures with pandas and matplotlib.

Three charts, the same ones the web page draws, as files you can drop into a
report:

  site-rainfall        the supplied daily rainfall sample, its fitted lognormal,
                       and the window accumulation that fit implies
  percentile           antecedent rainfall at each documented failure, ranked
                       against its own gauge's record for that season
  hyetograph           daily rain for the six weeks before one chosen failure

Usage
    python3 make_figures.py                       # all three, into ../figures
    python3 make_figures.py --figure percentile
    python3 make_figures.py --figure hyetograph --case leuwigajah2005
    python3 make_figures.py --outdir /tmp --format pdf --window 15

Reads site-rainfall.csv, landfill-failures.csv, antecedent-rainfall.csv/.json
from this directory. Run build_antecedent_rainfall.py first if they are missing.
"""

import argparse
import json
import os

import matplotlib
matplotlib.use("Agg")                     # write files, never open a window
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(HERE)

# the page's palette, so the figures and the page read as one thing
INK, INK2, INK3 = "#0F1618", "#48585C", "#718386"
LINE, PANEL = "#D6DFDF", "#FAFCFC"
BLAME = {
    "yes":     ("#eb6834", "rain blamed"),
    "partial": ("#9A6A16", "rain a contributing factor"),
    "no":      ("#2a78d6", "rain not implicated"),
    "unclear": ("#718386", "cause disputed"),
}

plt.rcParams.update({
    "figure.facecolor": PANEL, "axes.facecolor": PANEL, "savefig.facecolor": PANEL,
    "axes.edgecolor": INK3, "axes.labelcolor": INK2, "axes.titlecolor": INK,
    "xtick.color": INK3, "ytick.color": INK3, "text.color": INK,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": LINE, "grid.linewidth": 0.8,
    "font.size": 10, "axes.titlesize": 12, "axes.titleweight": "600",
    "figure.constrained_layout.use": True,
})


# ------------------------------------------------------------------ loading

def load_site_rainfall():
    """The supplied daily statistics, as a {statistic: value} Series."""
    df = pd.read_csv(os.path.join(HERE, "site-rainfall.csv"))
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df[df["kind"] == "observed"].set_index("statistic")["value"]


def load_failures():
    """Case list joined to its rainfall, one row per failure."""
    facts = pd.read_csv(os.path.join(HERE, "landfill-failures.csv"))
    rain = pd.read_csv(os.path.join(HERE, "antecedent-rainfall.csv"))
    keep = ["id", "short", "site", "city", "country", "reported_trigger",
            "rainfall_implicated"]
    return facts[keep].merge(rain.drop(columns=["site", "city", "country",
                                                "rainfall_implicated"]),
                             on="id", how="left")


def load_daily():
    """{id: [45 daily mm, oldest first]} — only the JSON carries the series."""
    with open(os.path.join(HERE, "antecedent-rainfall.json"), encoding="utf-8") as f:
        return {r["id"]: r.get("daily_mm") or [] for r in json.load(f)}


def lognormal_from_moments(mean, sd):
    """The mu, sigma of ln(X) that reproduce a given mean and sd of X."""
    sigma2 = np.log(1 + (sd / mean) ** 2)
    return np.log(mean) - sigma2 / 2, np.sqrt(sigma2)


# ------------------------------------------------------------------ figures

def fig_site_rainfall(window, samples, seed):
    """The supplied sample, the lognormal fitted to it, and what it accumulates to."""
    s = load_site_rainfall()
    mean, sd = s["mean"], s["standard_deviation"]
    mu, sigma = lognormal_from_moments(mean, sd)
    fit_median, fit_mode = np.exp(mu), np.exp(mu - sigma ** 2)

    rng = np.random.default_rng(seed)
    accum = rng.lognormal(mu, sigma, size=(samples, window)).sum(axis=1)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.4))

    # --- left: the daily distribution, and whether the fit holds ---
    # log x, because that is what turns a lognormal into a readable shape and
    # separates two medians that differ by only 2.6%
    x = np.logspace(np.log10(s["minimum"] * 0.7), np.log10(s["maximum"] * 1.4), 800)
    # density per unit ln(x), i.e. x*f(x). On a log axis this is the form whose
    # area is probability, and it is a symmetric bell centred on the median --
    # so the fit check is something you can see rather than have to be told.
    pdf = np.exp(-((np.log(x) - mu) ** 2) / (2 * sigma ** 2)) / (sigma * np.sqrt(2 * np.pi))
    ax1.plot(x, pdf, color="#eb6834", lw=2, zorder=3)
    ax1.fill_between(x, pdf, color="#eb6834", alpha=0.12, zorder=2)

    ax1.axvspan(s["minimum"], s["maximum"], color=INK3, alpha=0.06, zorder=1)
    ax1.axvline(s["median"], color=INK2, ls="--", lw=1.4, zorder=4)
    ax1.axvline(fit_median, color="#2a78d6", ls=":", lw=1.8, zorder=4)
    for v, lab in ((s["minimum"], "min"), (s["maximum"], "max")):
        ax1.axvline(v, color=INK3, lw=0.9, alpha=0.6, zorder=2)
        ax1.text(v, ax1.get_ylim()[1] * 0.02, f" {lab} {v:g}", rotation=90,
                 va="bottom", ha="left", fontsize=8, color=INK3)
    ax1.set_xscale("log")
    ax1.set_xlim(x[0], x[-1])
    ax1.set_xlabel("daily rainfall (mm/day, log scale)")
    ax1.set_ylabel("probability density per unit ln(rainfall)")
    ax1.set_title("Daily rainfall, fitted as a lognormal")

    ax1.legend(handles=[
        Line2D([], [], color="#eb6834", lw=2,
               label=f"lognormal  μ={mu:.4f}, σ={sigma:.4f}"),
        Line2D([], [], color=INK2, ls="--", lw=1.4,
               label=f"sample median {s['median']:.2f}"),
        Line2D([], [], color="#2a78d6", ls=":", lw=1.8,
               label=f"fitted median {fit_median:.3f}  (not used in fit)"),
    ], loc="upper left", frameon=False, fontsize=9)

    err = abs(fit_median - s["median"]) / s["median"] * 100
    ax1.text(0.98, 0.62,
             f"fitted from the mean and sd only\nmedian recovered to {err:.1f}%"
             f"\nmode of the density in x is {fit_mode:.3f},"
             f"\nagainst {s['mode']:.2f} reported — a binning artefact"
             "\nshaded: the observed range",
             transform=ax1.transAxes, ha="right", va="top", fontsize=8.5, color=INK2)

    # --- right: what that distribution accumulates to over the window ---
    hi = np.quantile(accum, 0.995)
    clipped = int((accum > hi).sum())
    ax2.hist(accum[accum <= hi], bins=46, color="#eb6834", alpha=0.55,
             edgecolor=PANEL, linewidth=0.4)
    for q, style in ((0.5, "--"), (0.9, ":"), (0.99, ":")):
        v = np.quantile(accum, q)
        if v > hi:
            continue
        ax2.axvline(v, color=INK2 if q == 0.5 else "#9A6A16", ls=style, lw=1.4)
        ax2.text(v, ax2.get_ylim()[1] * 0.97, f" {int(q*100)}th",
                 rotation=90, va="top", ha="left", fontsize=8.5, color=INK2)
    ax2.set_xlabel(f"rainfall accumulated over {window} days (mm)")
    ax2.set_ylabel("samples")
    ax2.set_title(f"{window}-day accumulation, {samples:,} draws")
    note = (f"median {np.median(accum):.0f} mm   mean {accum.mean():.0f} mm\n"
            "days drawn independently — no storm clustering")
    if clipped:
        note += f"\n{clipped} samples above {hi:.0f} mm not shown"
    ax2.text(0.98, 0.72, note, transform=ax2.transAxes, ha="right", va="top",
             fontsize=8.5, color=INK2)

    return fig, "site-rainfall"


def fig_percentile():
    """Where each failure's antecedent rainfall sat in its gauge's own record."""
    df = load_failures().sort_values("p7_pctl", ascending=True, na_position="first")

    fig, ax = plt.subplots(figsize=(10, 5.6))
    y = np.arange(len(df))

    for i, (_, r) in enumerate(df.iterrows()):
        colour = BLAME[r["rainfall_implicated"]][0]
        p7, p30 = r["p7_pctl"], r["p30_pctl"]
        if pd.isna(p7) and pd.isna(p30):
            msg = ("no gauge within 150 km" if pd.isna(r["station_id"])
                   else "record too short to rank")
            ax.text(2, i, msg, va="center", fontsize=8.5, color=INK3, style="italic")
            continue
        if not pd.isna(p7) and not pd.isna(p30):
            ax.plot([p30, p7], [i, i], color=colour, lw=1.5, alpha=0.5, zorder=2)
        if not pd.isna(p30):
            ax.scatter(p30, i, s=52, facecolor=PANEL, edgecolor=colour,
                       linewidth=1.8, zorder=3)
        if not pd.isna(p7):
            ax.scatter(p7, i, s=62, color=colour, edgecolor=PANEL,
                       linewidth=1.2, zorder=4)

    ax.axvline(50, color=INK3, ls="--", lw=1, alpha=0.6, zorder=1)
    ax.set_yticks(y, df["short"])
    ax.set_xlim(-2, 102)
    ax.set_ylim(-0.7, len(df) - 0.3)
    ax.set_xlabel("antecedent rainfall percentile for that gauge, that season")
    ax.set_title("What the rain was doing before twelve waste-slope failures")
    ax.grid(axis="y", visible=False)

    handles = [Line2D([], [], marker="o", ls="", color=c, label=w)
               for c, w in BLAME.values()]
    handles += [
        Line2D([], [], marker="o", ls="", color=INK3, label="filled = 7-day"),
        Line2D([], [], marker="o", ls="", markerfacecolor=PANEL,
               markeredgecolor=INK3, color=INK3, label="hollow = 30-day"),
    ]
    ax.legend(handles=handles, loc="lower right", frameon=False, fontsize=8.5,
              ncol=2)
    return fig, "antecedent-percentile"


def fig_hyetograph(case_id, window):
    """Daily rain for the six weeks up to one failure."""
    df = load_failures().set_index("id")
    daily = load_daily()
    if case_id not in df.index:
        raise SystemExit("unknown case %r — choose from: %s"
                         % (case_id, ", ".join(df.index)))
    r = df.loc[case_id]
    series = daily.get(case_id) or []
    if not series:
        raise SystemExit("%s has no daily record (no gauge was reporting)" % case_id)

    s = pd.Series(series, index=range(-(len(series) - 1), 1), name="mm")
    colour = BLAME[r["rainfall_implicated"]][0]

    fig, ax = plt.subplots(figsize=(10, 4.2))
    ax.bar(s.index, s.fillna(0), width=0.78, color=colour, alpha=0.85, zorder=3)

    # a day the gauge never reported is not a dry day, and must not look like one
    missing = s[s.isna()].index
    for d in missing:
        ax.axvspan(d - 0.45, d + 0.45, color=INK3, alpha=0.16, lw=0, zorder=2)
    if len(missing):
        ax.add_patch(plt.Rectangle((0, 0), 0, 0, color=INK3, alpha=0.16,
                                   label=f"{len(missing)} days not reported"))

    ax.axvspan(-window + 0.5, 0.5, color=colour, alpha=0.08, zorder=1)
    ax.axvline(-window + 0.5, color=colour, ls="--", lw=1, alpha=0.7, zorder=2)

    total = s.iloc[-window:].sum(skipna=True)
    seen = int(s.iloc[-window:].notna().sum())
    ax.set_xlabel("days before the slide")
    ax.set_ylabel("rainfall (mm/day)")
    ax.set_title(f"{r['site']} — {r['failure_date']}")
    ax.set_xlim(s.index[0] - 0.8, 0.8)
    ax.grid(axis="x", visible=False)
    ax.text(0.02, 0.95,
            f"{r['source']} gauge {str(r['station_name']).title()}, "
            f"{r['distance_km']:.0f} km away\n"
            f"shaded: last {window} days, {total:.0f} mm over {seen} reported days",
            transform=ax.transAxes, va="top", fontsize=8.5, color=INK2)
    if len(missing):
        ax.legend(loc="upper right", frameon=False, fontsize=8.5)
    return fig, f"hyetograph-{case_id}"


# ------------------------------------------------------------------ driver

def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--figure", default="all",
                    choices=["all", "site-rainfall", "percentile", "hyetograph"])
    ap.add_argument("--case", default="payatas2000", help="which failure to plot")
    ap.add_argument("--window", type=int, default=30, help="antecedent window, days")
    ap.add_argument("--samples", type=int, default=20000, help="Monte Carlo draws")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--outdir", default=os.path.join(PROJECT, "figures"))
    ap.add_argument("--format", default="png", choices=["png", "pdf", "svg"])
    ap.add_argument("--dpi", type=int, default=200)
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    wanted = (["site-rainfall", "percentile", "hyetograph"]
              if args.figure == "all" else [args.figure])

    for name in wanted:
        if name == "site-rainfall":
            fig, stem = fig_site_rainfall(args.window, args.samples, args.seed)
        elif name == "percentile":
            fig, stem = fig_percentile()
        else:
            fig, stem = fig_hyetograph(args.case, args.window)
        path = os.path.join(args.outdir, stem + "." + args.format)
        fig.savefig(path, dpi=args.dpi)
        plt.close(fig)
        print("wrote", path)


if __name__ == "__main__":
    main()
