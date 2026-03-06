import csv
import math
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

# ---------------------------------------------------------------------------
# Style constants
# ---------------------------------------------------------------------------
COLORS = {
    "Black":    "#C0392B",   # deep red
    "White":    "#2980B9",   # steel blue
    "Hispanic": "#7F8C8D",   # slate gray
    "Other":    "#BDC3C7",   # light gray
}
RACES = ["Black", "White", "Hispanic", "Other"]

def classify(ethnicity: str) -> str:
    e = ethnicity.strip()
    if e in {"Black", "Hispanic", "White"}:
        return e
    return "Other"


def apply_nyt_style(ax: plt.Axes, *, gridlines: bool = True) -> None:
    """Remove top/right spines; optional horizontal gridlines."""
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#AAAAAA")
    ax.spines["bottom"].set_color("#AAAAAA")
    ax.tick_params(colors="#444444", labelsize=9)
    if gridlines:
        ax.yaxis.grid(True, color="#E5E5E5", linewidth=0.7, zorder=0)
        ax.set_axisbelow(True)
    ax.xaxis.grid(False)


# ---------------------------------------------------------------------------
# One-pass data aggregation
# ---------------------------------------------------------------------------
data_path = Path(__file__).with_name("allegations_202007271729.csv")

# Plot 1 / 1v2: complaints per (year, race)
year_race_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

# Plot 2 / 2v2: per officer, complaints by race
officer_race_complaints: dict[str, dict[str, set]] = defaultdict(
    lambda: defaultdict(set)
)

# Plot 3: per officer in 2019, complaints by race
officer_2019_race: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

# Plot 4: per fado_type, complaints by race
fado_race_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

# Report: per year, per officer, Black/White complaint IDs + officer set
year_officer_black: dict[str, dict[str, set]] = defaultdict(lambda: defaultdict(set))
year_officer_white: dict[str, dict[str, set]] = defaultdict(lambda: defaultdict(set))
year_black_total: dict[str, set] = defaultdict(set)
year_white_total: dict[str, set] = defaultdict(set)
year_officers: dict[str, set] = defaultdict(set)

# Promotion report: per officer, rank snapshot
officer_rank_now: dict[str, str] = {}
officer_rank_incident: dict[str, set] = defaultdict(set)
promo_complaint_count = 0        # complaints where rank_incident="Police Officer" and rank_now != "Police Officer"
window_complaint_count = 0       # total complaints in window

# Overall top-10% removal report (all years combined, in window)
officer_black_all: dict[str, set] = defaultdict(set)    # Black complaint IDs per officer
all_black_all: set[str] = set()                         # all Black complaint IDs
officer_black_subst: dict[str, set] = defaultdict(set)  # substantiated Black complaint IDs per officer
all_black_subst: set[str] = set()                       # all substantiated Black complaint IDs
all_white_all: set[str] = set()                         # all White complaint IDs
all_white_subst: set[str] = set()                       # all substantiated White complaint IDs

# Plot 6: per year, per officer, complaints by race (all four)
year_officer_race: dict[str, dict[str, dict[str, set]]] = defaultdict(
    lambda: defaultdict(lambda: defaultdict(set))
)

with data_path.open(newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        mos_id        = (row.get("unique_mos_id") or "").strip()
        year          = (row.get("year_received") or "").strip()
        complaint_id  = (row.get("complaint_id") or "").strip()
        raw_eth       = (row.get("complainant_ethnicity") or "").strip()
        if raw_eth.lower() == "null" or not raw_eth:
            continue
        fado_type     = (row.get("fado_type") or "").strip()
        rank_inc      = (row.get("rank_incident") or "").strip()
        rank_now_val  = (row.get("rank_now") or "").strip()
        board_disp    = (row.get("board_disposition") or "").strip()
        race          = classify(raw_eth)
        is_subst      = board_disp.startswith("Substantiated")

        if not mos_id or not year or not complaint_id:
            continue

        in_window = year.isdigit() and 1999 <= int(year) < 2020

        if in_window:
            window_complaint_count += 1

            # Plots 1, 1v2
            year_race_counts[year][race] += 1

            # Plots 2, 2v2 (deduplicate per officer/race via complaint_id sets)
            officer_race_complaints[mos_id][race].add(complaint_id)

            # Plot 6
            year_officer_race[year][mos_id][race].add(complaint_id)

            # Plot 4
            if fado_type:
                fado_race_counts[fado_type][race] += 1

            # Report
            year_officers[year].add(mos_id)
            if race == "Black":
                year_officer_black[year][mos_id].add(complaint_id)
                year_black_total[year].add(complaint_id)
            elif race == "White":
                year_officer_white[year][mos_id].add(complaint_id)
                year_white_total[year].add(complaint_id)

            # Promotion report (rank fields)
            if rank_now_val:
                officer_rank_now[mos_id] = rank_now_val
            if rank_inc:
                officer_rank_incident[mos_id].add(rank_inc)
            if rank_inc == "Police Officer" and rank_now_val and rank_now_val != "Police Officer":
                promo_complaint_count += 1

            # Overall top-10% removal report
            if race == "Black":
                officer_black_all[mos_id].add(complaint_id)
                all_black_all.add(complaint_id)
                if is_subst:
                    officer_black_subst[mos_id].add(complaint_id)
                    all_black_subst.add(complaint_id)
            elif race == "White":
                all_white_all.add(complaint_id)
                if is_subst:
                    all_white_subst.add(complaint_id)

        # Plot 3 (always 2019, independent of window)
        if year == "2019":
            officer_2019_race[mos_id][race] += 1


# Module-level promoted / not-promoted officer lists (used by plot 5 and report)
promoted_officers:     list[str] = []
not_promoted_officers: list[str] = []
for _mos_id, _inc_ranks in officer_rank_incident.items():
    if "Police Officer" not in _inc_ranks:
        continue
    _current = officer_rank_now.get(_mos_id, "")
    if _current and _current != "Police Officer":
        promoted_officers.append(_mos_id)
    elif _current == "Police Officer":
        not_promoted_officers.append(_mos_id)


# ---------------------------------------------------------------------------
# Plot 1 — Multi-line: complaints over time by ethnicity
# ---------------------------------------------------------------------------
def make_plot1() -> None:
    years_sorted = sorted(y for y in year_race_counts if y.isdigit())
    xs = [int(y) for y in years_sorted]

    fig, ax = plt.subplots(figsize=(10, 5.5))
    apply_nyt_style(ax)
    ax.tick_params(labelsize=12)

    for race in RACES:
        ys = [year_race_counts[y].get(race, 0) for y in years_sorted]
        ax.plot(xs, ys, color=STACK_COLORS[race], linewidth=2, label=race, solid_capstyle="round")

        # Label at right endpoint
        last_y = ys[-1]
        ax.annotate(
            race,
            xy=(xs[-1], last_y),
            xytext=(8, 0),
            textcoords="offset points",
            va="center",
            fontsize=11,
            color=STACK_COLORS[race],
            fontfamily="DejaVu Sans",
        )

    # Set x-axis limit to end at 2020
    ax.set_xlim(xs[0] - 1, 2020)
    ax.xaxis.set_major_locator(mticker.MultipleLocator(5))
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: str(int(x))))
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{int(x):,}"))
    ax.set_xlabel("Year", fontsize=13, color="#444444")
    ax.set_ylabel("Number of complaints", fontsize=13, color="#444444")

    ax.set_title(
        "Complaints by complainant ethnicity over time",
        fontsize=20, fontweight="bold", color="#111111", loc="left", pad=14,
        fontfamily="Georgia",
    )
    ax.text(
        0, 0.99, "NYPD civilian complaint data, 1999–2019",
        transform=ax.transAxes, fontsize=13, color="#777777",
    )

    fig.tight_layout()
    out = Path(__file__).with_name("vis_plot1_time.png")
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Plot 1 saved → {out}")


# ---------------------------------------------------------------------------
# Plot 2 — Diverging-bar ratio histogram (Black / White per officer)
# ---------------------------------------------------------------------------
def make_plot2() -> None:
    ratios: list[float] = []
    no_white_count = 0

    for mos_id, by_race in officer_race_complaints.items():
        n_black = len(by_race.get("Black", set()))
        n_white = len(by_race.get("White", set()))
        if n_white == 0:
            no_white_count += 1
        else:
            ratios.append(n_black / n_white)

    # Build bins: 0–0.5, 0.5–1, 1–2, 2–3, 3–4, 4–5, 5–7, 7–10, 10+
    bin_edges = [0, 0.5, 1, 2, 3, 4, 5, 7, 10, float("inf")]
    bin_labels = ["0–0.5", "0.5–1", "1–2", "2–3", "3–4", "4–5", "5–7", "7–10", "10+"]
    counts = [0] * len(bin_labels)
    for r in ratios:
        for i, (lo, hi) in enumerate(zip(bin_edges[:-1], bin_edges[1:])):
            if lo <= r < hi:
                counts[i] += 1
                break

    # Midpoints for color decision
    bin_mids = [0.25, 0.75, 1.5, 2.5, 3.5, 4.5, 6, 8.5, 12]
    bar_colors = ["#2980B9" if m < 1 else "#C0392B" for m in bin_mids]

    # Add "No white" entry
    all_labels = bin_labels + ["No\nwhite"]
    all_counts = counts + [no_white_count]
    all_colors = bar_colors + ["#BDC3C7"]

    # Positions: leave a gap before the "No white" bar
    n_bins = len(bin_labels)
    positions = list(range(n_bins)) + [n_bins + 1]

    fig, ax = plt.subplots(figsize=(12, 5.5))
    apply_nyt_style(ax)

    bars = ax.bar(positions, all_counts, color=all_colors, width=0.75, zorder=3,
                  edgecolor="white", linewidth=0.4)

    ymax = max(all_counts) * 1.1
    ax.set_ylim(0, ymax)

    # Baseline at ratio = 1 (between bin index 1 and 2)
    ax.axvline(x=1.5, color="#444444", linewidth=1.2, linestyle="--", alpha=0.5)
    ax.text(0.35, ymax * 0.95, "More White", fontsize=8.5,
            color="#2980B9", ha="center", va="top")
    ax.text(2.65, ymax * 0.95, "More Black", fontsize=8.5,
            color="#C0392B", ha="center", va="top")

    ax.set_xticks(positions)
    ax.set_xticklabels(all_labels, fontsize=8.5)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{int(x):,}"))
    ax.set_xlabel("Black / White complainant ratio (per officer)", fontsize=10, color="#444444")
    ax.set_ylabel("Number of officers", fontsize=10, color="#444444")

    ax.set_title(
        "Distribution of Black-to-White complainant ratio per officer",
        fontsize=22, fontweight="bold", color="#111111", loc="left", pad=12,
        fontfamily="Georgia",
    )
    ax.text(
        0, 1.01, "NYPD civilian complaint data, 1999–2019",
        transform=ax.transAxes, fontsize=13, color="#777777",
    )

    ymax = max(all_counts) * 1.1
    ax.set_ylim(0, ymax)

    fig.tight_layout()
    out = Path(__file__).with_name("vis_plot2_ratio.png")
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Plot 2 saved → {out}")


# ---------------------------------------------------------------------------
# Plot 3 — Stacked area chart, 2019 officers
# ---------------------------------------------------------------------------
# Stack order (bottom → top): White, Other, Hispanic, Black
# Color families: cool blues (White/Other) at base, warm reds (Hispanic/Black) on top
STACK_ORDER  = ["White", "Other", "Hispanic", "Black"]
STACK_COLORS = {
    "White":    "#2980B9",   # steel blue
    "Other":    "#7FB3D3",   # light blue
    "Hispanic": "#E59866",   # warm orange
    "Black":    "#C0392B",   # deep red
}

def make_plot3() -> None:
    officers = list(officer_2019_race.keys())

    def sort_key(mos_id: str) -> tuple:
        d = officer_2019_race[mos_id]
        return (
            d.get("Black", 0),
            d.get("White", 0),
            d.get("Hispanic", 0),
            d.get("Other", 0),
        )

    officers.sort(key=sort_key)
    n = len(officers)
    xs = np.arange(n)

    fig, ax = plt.subplots(figsize=(14, 5.5))
    apply_nyt_style(ax, gridlines=True)

    # Build stacked data arrays in stack order
    data = np.array(
        [[officer_2019_race[o].get(race, 0) for o in officers] for race in STACK_ORDER],
        dtype=float,
    )

    polys = ax.stackplot(
        xs, data,
        colors=[STACK_COLORS[r] for r in STACK_ORDER],
        alpha=0.88,
        linewidth=0,
    )

    # Direct band labels: place near the right edge of the chart
    label_x = int(n * 0.88)
    cumulative = np.zeros(n)
    for i, race in enumerate(STACK_ORDER):
        band_bottom = cumulative[label_x]
        band_top    = band_bottom + data[i][label_x]
        band_height = band_top - band_bottom
        cumulative += data[i]
        if band_height < 0.4:
            continue
        mid_y = (band_bottom + band_top) / 2
        ax.annotate(
            race,
            xy=(label_x, mid_y),
            xytext=(6, 0),
            textcoords="offset points",
            va="center",
            ha="left",
            fontsize=9,
            color="white",
            fontweight="bold",
        )

    ax.set_xlim(0, n - 1)
    ax.set_xticks([])
    ax.set_xlabel(f"Officers with complaints in 2019 (n={n})", fontsize=10, color="#444444")
    ax.set_ylabel("Number of complaints", fontsize=10, color="#444444")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{int(x):,}"))

    ax.set_title(
        "Complaints per officer in 2019, by complainant ethnicity",
        fontsize=22, fontweight="bold", color="#111111", loc="left", pad=12,
        fontfamily="Georgia",
    )
    ax.text(
        0, 1.01, "Sorted by total complaints (least → most); officers with 2019 complaints only",
        transform=ax.transAxes, fontsize=12, color="#777777",
    )

    fig.tight_layout()
    out = Path(__file__).with_name("vis_plot3_2019.png")
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Plot 3 saved → {out}")


# ---------------------------------------------------------------------------
# Plot 1v2 — Stacked area: complaints over time by ethnicity
# ---------------------------------------------------------------------------
def make_plot1_v2() -> None:
    years_sorted = sorted(y for y in year_race_counts if y.isdigit())
    xs = [int(y) for y in years_sorted]

    fig, ax = plt.subplots(figsize=(11, 5.5))
    apply_nyt_style(ax, gridlines=True)

    data = np.array(
        [[year_race_counts[y].get(race, 0) for y in years_sorted] for race in STACK_ORDER],
        dtype=float,
    )

    ax.stackplot(
        xs, data,
        colors=[STACK_COLORS[r] for r in STACK_ORDER],
        alpha=0.88,
        linewidth=0,
    )

    # Direct band labels at the right edge
    cumulative = np.zeros(len(xs))
    for i, race in enumerate(STACK_ORDER):
        band_bottom = cumulative[-1]
        band_top    = band_bottom + data[i][-1]
        cumulative += data[i]
        if band_top - band_bottom < 30:
            continue
        ax.annotate(
            race,
            xy=(xs[-1], (band_bottom + band_top) / 2),
            xytext=(8, 0),
            textcoords="offset points",
            va="center",
            ha="left",
            fontsize=9,
            color=STACK_COLORS[race],
            fontweight="bold",
        )

    ax.set_xlim(xs[0], xs[-1] + 3)
    ax.xaxis.set_major_locator(mticker.MultipleLocator(5))
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: str(int(x))))
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{int(x):,}"))
    ax.set_xlabel("Year", fontsize=10, color="#444444")
    ax.set_ylabel("Number of complaints (stacked)", fontsize=10, color="#444444")

    ax.set_title(
        "Total complaints over time, stacked by complainant ethnicity",
        fontsize=22, fontweight="bold", color="#111111", loc="left", pad=12,
        fontfamily="Georgia",
    )
    ax.text(
        0, 1.01, "NYPD civilian complaint data, 1999–2019",
        transform=ax.transAxes, fontsize=13, color="#777777",
    )

    fig.tight_layout()
    out = Path(__file__).with_name("vis_plot1_v2_stacked.png")
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Plot 1v2 saved → {out}")


# ---------------------------------------------------------------------------
# Plot 2v2 — Diverging bars: Black − White complaint difference per officer
# ---------------------------------------------------------------------------
def make_plot2_v2() -> None:
    diffs: list[int] = []
    for mos_id, by_race in officer_race_complaints.items():
        n_black = len(by_race.get("Black", set()))
        n_white = len(by_race.get("White", set()))
        diffs.append(n_black - n_white)

    diffs.sort()
    xs = np.arange(len(diffs))
    diffs_arr = np.array(diffs)

    colors = np.where(diffs_arr >= 0, "#C0392B", "#2980B9")

    fig, ax = plt.subplots(figsize=(14, 5.5))
    apply_nyt_style(ax, gridlines=False)

    ax.bar(xs, diffs_arr, color=colors, width=1.0, linewidth=0, zorder=3)
    ax.axhline(0, color="#444444", linewidth=1.0, zorder=4)

    # Horizontal reference lines
    ymax = max(abs(diffs_arr.min()), diffs_arr.max())
    for ref in [5, 10, 20, -5, -10]:
        if abs(ref) <= ymax * 0.95:
            ax.axhline(ref, color="#E5E5E5", linewidth=0.7, zorder=0)
            ax.text(len(diffs) * 1.002, ref, f"{ref:+d}",
                    va="center", fontsize=8, color="#999999")

    # Annotate regions
    zero_idx = int(np.searchsorted(diffs_arr, 0))
    ax.text(zero_idx * 0.45, ymax * 0.88, "More White complainants",
            fontsize=9, color="#2980B9", ha="center", fontweight="bold")
    ax.text(zero_idx + (len(diffs) - zero_idx) * 0.55, ymax * 0.88, "More Black complainants",
            fontsize=9, color="#C0392B", ha="center", fontweight="bold")

    ax.set_xlim(-1, len(diffs))
    ax.set_xticks([])
    ax.set_xlabel(
        f"Each bar = one officer (n={len(diffs):,}), sorted by difference",
        fontsize=10, color="#444444",
    )
    ax.set_ylabel("Black − White complaints", fontsize=10, color="#444444")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{int(x):+,}"))
    ax.spines["bottom"].set_visible(False)

    ax.set_title(
        "Black minus White complainants per officer",
        fontsize=22, fontweight="bold", color="#111111", loc="left", pad=12,
        fontfamily="Georgia",
    )
    ax.text(
        0, 1.01, "NYPD civilian complaint data, 1999–2019",
        transform=ax.transAxes, fontsize=13, color="#777777",
    )

    fig.tight_layout()
    out = Path(__file__).with_name("vis_plot2_v2_diff.png")
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Plot 2v2 saved → {out}")


# ---------------------------------------------------------------------------
# Plot 4 — Horizontal % stacked bars by FADO type and complainant race
# ---------------------------------------------------------------------------
def make_plot4() -> None:
    # Fixed row order; fall back to any remaining types with enough counts
    preferred_order = ["Force", "Abuse of Authority", "Offensive Language", "Discourtesy"]
    all_types = {ft for ft, counts in fado_race_counts.items() if sum(counts.values()) >= 50}
    fado_types = [ft for ft in preferred_order if ft in all_types] + \
                 sorted(all_types - set(preferred_order))

    # Percentage matrix: rows = fado_type, cols = STACK_ORDER
    pcts: dict[str, dict[str, float]] = {}
    for ft in fado_types:
        total = sum(fado_race_counts[ft].values())
        pcts[ft] = {race: fado_race_counts[ft].get(race, 0) / total * 100
                    for race in STACK_ORDER}

    n_rows = len(fado_types)
    # Long-and-thin layout: fixed short height, custom vertical spacing
    bar_height = 0.35
    row_gap = 0.10
    ys = np.arange(n_rows) * (bar_height + row_gap)

    fig, ax = plt.subplots(figsize=(10, 4.5))
    apply_nyt_style(ax, gridlines=False)
    ax.tick_params(labelsize=12)

    lefts = np.zeros(n_rows)

    for race in STACK_ORDER:
        widths = np.array([pcts[ft][race] for ft in fado_types])
        bars = ax.barh(ys, widths, left=lefts, height=bar_height,
                       color=STACK_COLORS[race], linewidth=0)
        # Label inside each segment if wide enough
        for j, (w, l) in enumerate(zip(widths, lefts)):
            if w >= 4:
                ax.text(
                    l + w / 2, ys[j], f"{w:.0f}%",
                    ha="center", va="center", fontsize=8.5,
                    color="white", fontweight="bold",
                )
        lefts += widths

    ax.set_yticks(ys)
    ax.set_yticklabels(fado_types, fontsize=13, color="#333333")
    ax.set_xlim(0, 100)
    ax.set_xlabel("Share of complaints (%)", fontsize=13, color="#444444")
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{int(x)}%"))
    ax.spines["left"].set_visible(False)
    ax.tick_params(left=False)
    ax.invert_yaxis()

    # Column headers (race labels) — draw just below the bars
    cumulative_x = 0.0
    for race in STACK_ORDER:
        mid = cumulative_x + np.mean([pcts[fado_types[0]][race]]) / 2
        ax.text(
            mid,
            -(bar_height + row_gap-0.3),
            race,
            ha="center",
            va="bottom",
            fontsize=9,
            color=STACK_COLORS[race],
            fontweight="bold",
            transform=ax.get_xaxis_transform(),
        )
        cumulative_x += np.mean([pcts[fado_types[0]][race]])

    ax.set_title(
        "Complainant ethnicity breakdown by allegation type",
        fontsize=20, fontweight="bold", color="#111111", loc="left", pad=25,
        fontfamily="Georgia",
    )
    ax.text(
        0, 1.02, "NYPD civilian complaint data, 1999–2019",
        transform=ax.transAxes, fontsize=13, color="#777777",
    )

    # Manual layout so ethnicity labels can sit close to the bottom
    fig.subplots_adjust(left=0.20, right=0.98, top=0.75, bottom=0.24)
    out = Path(__file__).with_name("vis_plot4_fado.png")
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(f"Plot 4 saved → {out}")


# ---------------------------------------------------------------------------
# Plot 5 — Stacked bars: complaint ethnicity breakdown, promoted vs not promoted
# Bar heights = absolute complaint counts; segment labels = % (colors match plot 1)
# ---------------------------------------------------------------------------
def make_plot5() -> None:
    groups = [
        ("Promoted",     promoted_officers),
        ("Not Promoted", not_promoted_officers),
    ]

    # Counts by race per group (absolute numbers); order = STACK_ORDER (White, Other, Hispanic, Black)
    group_counts: dict[str, dict[str, int]] = {}
    for label, officers in groups:
        counts = {r: sum(len(officer_race_complaints[o].get(r, set())) for o in officers)
                  for r in STACK_ORDER}
        group_counts[label] = counts

    # Percentages for in-segment labels
    group_pcts: dict[str, dict[str, float]] = {}
    for label, officers in groups:
        counts = group_counts[label]
        grand = sum(counts.values()) or 1
        group_pcts[label] = {r: counts[r] / grand * 100 for r in STACK_ORDER}

    fig, ax = plt.subplots(figsize=(10, 6.0))
    apply_nyt_style(ax, gridlines=True)
    ax.tick_params(labelsize=12)

    xs = np.arange(len(groups))
    bar_w = 0.5
    bottoms = np.zeros(len(groups))

    for race in STACK_ORDER:
        heights = np.array([group_counts[lbl][race] for lbl, _ in groups], dtype=float)
        ax.bar(xs, heights, bottom=bottoms, width=bar_w,
               color=STACK_COLORS[race], linewidth=0, zorder=3)
        bottoms += heights

    y_max = bottoms.max() * 1.08
    bar_totals = np.array([sum(group_counts[lbl][r] for r in STACK_ORDER) for lbl, _ in groups])

    # Add percentage labels to segments (after bottoms finalised)
    bottoms = np.zeros(len(groups))
    for race in STACK_ORDER:
        heights = np.array([group_counts[lbl][race] for lbl, _ in groups], dtype=float)
        for j, (h, b) in enumerate(zip(heights, bottoms)):
            if h >= 0.04 * bar_totals[j]:  # show % if segment is at least 4% of bar
                pct = group_pcts[groups[j][0]][race]
                ax.text(xs[j], b + h / 2, f"{pct:.1f}%",
                        ha="center", va="center", fontsize=9,
                        color="white", fontweight="bold")
        bottoms += heights
    ax.set_xlim(-0.5, len(groups) - 0.5)
    ax.set_ylim(0, y_max)
    ax.set_xticks(xs)
    ax.set_xticklabels(
        [f"{lbl}\n(n={len(officers):,})" for lbl, officers in groups],
        fontsize=13, color="#333333",
    )
    ax.set_ylabel("Number of complaints", fontsize=13, color="#444444")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{int(x):,}"))

    # Legend: STACK_ORDER / STACK_COLORS (aligned with other plots)
    handles = [plt.Rectangle((0, 0), 1, 1, color=STACK_COLORS[r]) for r in STACK_ORDER]
    ax.legend(
        handles, STACK_ORDER,
        loc="upper right",
        frameon=False,
        fontsize=11,
        title="Complainant ethnicity",
        title_fontsize=12,
    )

    ax.set_title(
        "Complainant ethnicity breakdown:\npromoted vs. not-promoted officers",
        fontsize=20, fontweight="bold", color="#111111", loc="left", pad=20,
        fontfamily="Georgia",
    )
    ax.text(
        0, 1.0, "Officers who were Police Officer at incident; 1999–2019",
        transform=ax.transAxes, fontsize=12, color="#777777",
    )

    fig.tight_layout()
    out = Path(__file__).with_name("vis_plot5_promo.png")
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Plot 5 saved → {out}")


# ---------------------------------------------------------------------------
# Plot 2v3 — Histogram of (Black − White) complaint difference per officer
# ---------------------------------------------------------------------------
def make_plot2_v3() -> None:
    diffs: list[int] = []
    for by_race in officer_race_complaints.values():
        n_black = len(by_race.get("Black", set()))
        n_white = len(by_race.get("White", set()))
        diffs.append(n_black - n_white)

    diffs_arr = np.array(diffs)
    lo, hi = int(diffs_arr.min()), int(diffs_arr.max())

    # Bin width of 1 so every integer difference gets its own bar
    bins = np.arange(lo - 0.5, hi + 1.5, 1)
    counts, edges = np.histogram(diffs_arr, bins=bins)
    centers = (edges[:-1] + edges[1:]) / 2

    bar_colors = ["#C0392B" if c >= 0 else "#2980B9" for c in centers]

    fig, ax = plt.subplots(figsize=(13, 5.5))
    apply_nyt_style(ax, gridlines=True)

    ax.bar(centers, counts, width=0.85, color=bar_colors, linewidth=0, zorder=3)
    ax.axvline(0, color="#444444", linewidth=1.2, zorder=4)

    # Shade and label the two halves
    ymax = counts.max() * 1.15
    ax.axvspan(lo - 1, 0, alpha=0.04, color="#2980B9", zorder=0)
    ax.axvspan(0, hi + 1, alpha=0.04, color="#C0392B", zorder=0)
    ax.text(-0.5, ymax * 0.96, "More White", ha="right", va="top",
            fontsize=9, color="#2980B9", fontweight="bold")
    ax.text( 0.5, ymax * 0.96, "More Black", ha="left",  va="top",
            fontsize=9, color="#C0392B", fontweight="bold")

    ax.set_xlim(lo - 1, hi + 1)
    ax.set_ylim(0, ymax)
    ax.xaxis.set_major_locator(mticker.MaxNLocator(integer=True))
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{int(x):,}"))
    ax.set_xlabel("Black − White complainants (per officer)", fontsize=10, color="#444444")
    ax.set_ylabel("Number of officers", fontsize=10, color="#444444")

    ax.set_title(
        "Distribution of Black minus White complainants per officer",
        fontsize=22, fontweight="bold", color="#111111", loc="left", pad=12,
        fontfamily="Georgia",
    )
    ax.text(
        0, 1.01, "NYPD civilian complaint data, 1999–2019",
        transform=ax.transAxes, fontsize=13, color="#777777",
    )

    fig.tight_layout()
    out = Path(__file__).with_name("vis_plot2_v3_diff_hist.png")
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Plot 2v3 saved → {out}")


# ---------------------------------------------------------------------------
# Report — per-year top-10% removal impact + avg Black vs White per officer
# ---------------------------------------------------------------------------
def print_report() -> None:
    # --- Section 1: top-10% removal impact ---
    print()
    print(f"{'Year':<6} {'Total Black':>13} {'After remove top 10%':>22} {'Reduction ratio':>17}")
    print("-" * 62)

    for year in sorted(year_officer_black.keys()):
        total_set = year_black_total[year]
        total = len(total_set)
        if total == 0:
            continue

        officer_map = year_officer_black[year]
        officers_sorted = sorted(officer_map.items(), key=lambda kv: len(kv[1]), reverse=True)
        top_n = max(1, math.ceil(len(officers_sorted) * 0.10))
        top_officers = {mos_id for mos_id, _ in officers_sorted[:top_n]}

        removed_complaints: set[str] = set()
        for mos_id in top_officers:
            removed_complaints.update(officer_map[mos_id])

        after = len(total_set - removed_complaints)
        ratio = 1 - after / total
        print(f"{year:<6} {total:>13,} {after:>22,} {ratio:>16.3f}")

    # --- Section 2: avg Black vs White complainants per officer per year ---
    print()
    print(f"{'Year':<6} {'Officers':>10} {'Avg Black':>11} {'Avg White':>11} {'Ratio B/W':>11}")
    print("-" * 53)

    years_window = sorted(y for y in year_officers if y.isdigit())
    total_black_all = total_white_all = total_officer_years = 0

    for year in years_window:
        n_officers = len(year_officers[year])
        if n_officers == 0:
            continue
        n_black = len(year_black_total.get(year, set()))
        n_white = len(year_white_total.get(year, set()))
        avg_b = n_black / n_officers
        avg_w = n_white / n_officers
        ratio_bw = avg_b / avg_w if avg_w else float("inf")
        print(f"{year:<6} {n_officers:>10,} {avg_b:>11.2f} {avg_w:>11.2f} {ratio_bw:>11.2f}")
        total_black_all    += n_black
        total_white_all    += n_white
        total_officer_years += n_officers

    if total_officer_years:
        avg_b_all = total_black_all  / total_officer_years
        avg_w_all = total_white_all  / total_officer_years
        ratio_all = avg_b_all / avg_w_all if avg_w_all else float("inf")
        print("-" * 53)
        print(f"{'Overall':<6} {total_officer_years:>10,} {avg_b_all:>11.2f} {avg_w_all:>11.2f} {ratio_all:>11.2f}")

    # --- Section 3: overall top-10% removal (all years combined) ---
    def _top10_removal(officer_map: dict, all_complaints: set) -> tuple[int, int, float]:
        total = len(all_complaints)
        if total == 0:
            return 0, 0, 0.0
        ranked = sorted(officer_map.items(), key=lambda kv: len(kv[1]), reverse=True)
        top_n  = max(1, math.ceil(len(ranked) * 0.10))
        removed: set[str] = set()
        for mos_id, ids in ranked[:top_n]:
            removed.update(ids)
        after = len(all_complaints - removed)
        return total, after, 1 - after / total

    print()
    print("=== Overall top-10% officer removal (all years combined) ===")
    print()
    print(f"{'Scope':<22} {'Black':>8} {'White':>8} {'After remove top 10% (Black)':>30} {'Reduction':>11}")
    print("-" * 82)

    tot, aft, red = _top10_removal(officer_black_all, all_black_all)
    print(f"{'All complaints':<22} {tot:>8,} {len(all_white_all):>8,} {aft:>30,} {red:>10.1%}")

    tot_s, aft_s, red_s = _top10_removal(officer_black_subst, all_black_subst)
    print(f"{'Substantiated only':<22} {tot_s:>8,} {len(all_white_subst):>8,} {aft_s:>30,} {red_s:>10.1%}")

    # --- Section 4: promotion report ---
    print()
    print("=== Promotion report (rank_incident = 'Police Officer', 1999–2019) ===")
    print()

    # Complaint-level counts
    if window_complaint_count:
        pct = promo_complaint_count / window_complaint_count * 100
        print(f"Complaints where officer was Police Officer at incident and has since been promoted:")
        print(f"  {promo_complaint_count:,} of {window_complaint_count:,} total complaints "
              f"({pct:.1f}%)")
    print()

    print(f"Officers who were Police Officer at incident time and have been promoted: "
          f"{len(promoted_officers):,}")
    print(f"Officers who were Police Officer at incident time and remain Police Officer: "
          f"{len(not_promoted_officers):,}")
    print()

    def complaint_counts(officers: list[str]) -> int:
        """Return total number of complaints against a list of officers (all races)."""
        return sum(
            sum(len(race_complaints) for race_complaints in officer_race_complaints[o].values())
            for o in officers
        )

    promoted_complaints = complaint_counts(promoted_officers)
    not_promoted_complaints = complaint_counts(not_promoted_officers)

    print(f"Total complaints involving promoted officers:     {promoted_complaints:,}")
    print(f"Total complaints involving not-promoted officers: {not_promoted_complaints:,}")
    print()

    def avg_race_breakdown(officers: list[str]) -> dict[str, float]:
        if not officers:
            return {r: 0.0 for r in RACES}
        totals = {r: sum(len(officer_race_complaints[o].get(r, set())) for o in officers)
                  for r in RACES}
        grand = sum(totals.values()) or 1
        return {r: totals[r] / grand * 100 for r in RACES}

    promo_pct  = avg_race_breakdown(promoted_officers)
    npromo_pct = avg_race_breakdown(not_promoted_officers)

    print(f"{'Race':<12}  {'Promoted':>10}  {'Not promoted':>12}")
    print("-" * 38)
    for race in RACES:
        print(f"{race:<12}  {promo_pct[race]:>9.1f}%  {npromo_pct[race]:>11.1f}%")


# ---------------------------------------------------------------------------
# Plot 6 — Mean ± SD complaint bars per year, by complainant ethnicity
# ---------------------------------------------------------------------------
def make_plot6() -> None:
    import matplotlib.colors as mcolors

    def lighten(hex_color: str, amount: float = 0.55) -> tuple:
        """Blend color toward white by `amount` (0 = original, 1 = white)."""
        rgb = mcolors.to_rgb(hex_color)
        return tuple(c + (1 - c) * amount for c in rgb)

    years_sorted = [str(y) for y in range(1999, 2020)]

    # Layout geometry
    bar_w     = 0.15   # width of each individual bar
    intra_gap = 0.04   # gap between bars within a year-group
    inter_gap = 0.22   # gap between year-groups
    group_w   = len(RACES) * bar_w + (len(RACES) - 1) * intra_gap

    # Pre-compute x-positions for each bar and group-centre ticks
    group_centers: list[float] = []
    bar_xs: dict[str, dict[str, float]] = {}   # bar_xs[year][race] = x centre

    for i, year in enumerate(years_sorted):
        group_left = i * (group_w + inter_gap)
        group_centers.append(group_left + group_w / 2)
        bar_xs[year] = {}
        for j, race in enumerate(RACES):
            bar_xs[year][race] = group_left + j * (bar_w + intra_gap) + bar_w / 2

    # Collect means for printing
    means_table: dict[str, dict[str, float]] = defaultdict(dict)

    fig, ax = plt.subplots(figsize=(10, 5.5))
    apply_nyt_style(ax)
    ax.tick_params(labelsize=12)

    for year in years_sorted:
        officers_this_year = year_officers.get(year, set())
        if not officers_this_year:
            continue

        for race in RACES:
            counts = np.array([
                len(year_officer_race[year][mos_id].get(race, set()))
                for mos_id in officers_this_year
            ], dtype=float)

            mean = counts.mean()
            sd   = counts.std(ddof=1) if len(counts) > 1 else 0.0
            means_table[year][race] = mean

            xc       = bar_xs[year][race]
            full_col = STACK_COLORS[race]
            lite_col = lighten(full_col)

            lo_2sd = max(0.0, mean - 2 * sd)
            hi_2sd = mean + 2 * sd
            lo_1sd = max(0.0, mean - sd)
            hi_1sd = mean + sd

            # Outer desaturated band: mean ± 2 SD
            if hi_2sd > lo_2sd:
                ax.bar(xc, hi_2sd - lo_2sd, bottom=lo_2sd,
                       width=bar_w, color=lite_col, linewidth=0, zorder=2)

            # Inner full-color band: mean ± 1 SD
            if hi_1sd > lo_1sd:
                ax.bar(xc, hi_1sd - lo_1sd, bottom=lo_1sd,
                       width=bar_w, color=full_col, linewidth=0, zorder=3)

            # White mean line
            ax.plot(
                [xc - bar_w / 2, xc + bar_w / 2],
                [mean, mean],
                color="white", linewidth=1.2, zorder=4,
                solid_capstyle="butt",
            )

    # Print mean complaints per officer per ethnicity per year
    print("\n--- Plot 6: Mean complaints per officer, by year and complainant ethnicity ---")
    header = f"{'Year':<6}" + "".join(f" {r:>10}" for r in RACES)
    print(header)
    print("-" * len(header))
    for year in years_sorted:
        row_vals = [means_table[year].get(r, float("nan")) for r in RACES]
        row_str = f"{year:<6}" + "".join(f" {v:>10.3f}" for v in row_vals)
        print(row_str)
    print()

    # X-axis: one tick per year group, label every 3 years
    ax.set_xticks(group_centers)
    tick_labels = [
        year if (int(year) - 1999) % 3 == 0 else ""
        for year in years_sorted
    ]
    ax.set_xticklabels(tick_labels, fontsize=12, color="#444444")
    ax.set_xlim(-inter_gap / 2, group_centers[-1] + group_w / 2 + inter_gap / 2)

    ax.set_ylabel("Complaints per officer", fontsize=13, color="#444444")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{int(x):,}"))

    # Legend: one swatch per race (full color)
    handles = [
        plt.Rectangle((0, 0), 1, 1, color=STACK_COLORS[r], label=r)
        for r in RACES
    ]
    ax.legend(
        handles=handles,
        loc="upper right",
        frameon=False,
        fontsize=11,
        title="Complainant ethnicity",
        title_fontsize=12,
    )

    ax.set_title(
        "Complaints per officer per year, by complainant ethnicity",
        fontsize=20, fontweight="bold", color="#111111", loc="left", pad=14,
        fontfamily="Georgia",
    )
    ax.text(
        0, 0.99,
        "Bars show mean ± 2 SD (light) and mean ± 1 SD (dark) across officers active each year; "
        "white line = mean",
        transform=ax.transAxes, fontsize=11, color="#777777",
    )

    fig.tight_layout()
    out = Path(__file__).with_name("vis_plot6_percentile.png")
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Plot 6 saved → {out}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    make_plot1()
    make_plot1_v2()
    make_plot2()
    make_plot2_v2()
    make_plot3()
    make_plot4()
    make_plot5()
    make_plot6()
    make_plot2_v3()
    print_report()
