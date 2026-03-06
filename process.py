import csv
import math
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import seaborn as sns


def main() -> None:
    data_path = Path(__file__).with_name("allegations_202007271729.csv")

    officer_to_complaints: dict[str, set[str]] = defaultdict(set)
    all_black_complaints: set[str] = set()

    # Track complaints per officer by complainant race (for histogram)
    officer_complaints_by_race: dict[str, dict[str, set[str]]] = defaultdict(
        lambda: defaultdict(set)
    )

    # Per-year tracking
    year_officer_to_complaints: dict[str, dict[str, set[str]]] = defaultdict(
        lambda: defaultdict(set)
    )
    year_all_black_complaints: dict[str, set[str]] = defaultdict(set)

    with data_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ethnicity = (row.get("complainant_ethnicity") or "").strip()
            mos_id = (row.get("unique_mos_id") or "").strip()
            year = (row.get("year_received") or "").strip()
            complaint_id = (row.get("complaint_id") or "").strip()
            if not mos_id or not complaint_id or not year:
                continue

            # For Black-only calculations used elsewhere in the script
            if ethnicity == "Black":
                officer_to_complaints[mos_id].add(complaint_id)
                all_black_complaints.add(complaint_id)
                year_officer_to_complaints[year][mos_id].add(complaint_id)
                year_all_black_complaints[year].add(complaint_id)

            # For the stacked histogram: track both Black and White complaints per officer
            if ethnicity in {"Black", "White"}:
                officer_complaints_by_race[mos_id][ethnicity].add(complaint_id)

    total_black_complaints = len(all_black_complaints)

    if not officer_to_complaints:
        print("Total complaints from Black complainants: 0")
        print(
            "Total complaints from Black complainants after removing top 10% officers: 0"
        )
        return

    # Determine officers with the highest numbers of complaints from Black complainants
    officers_sorted = sorted(
        officer_to_complaints.items(), key=lambda kv: len(kv[1]), reverse=True
    )
    num_officers = len(officers_sorted)
    top_count = max(1, math.ceil(num_officers * 0.10))
    top_officers = {mos_id for mos_id, _ in officers_sorted[:top_count]}

    # Complaint-count distribution per officer (Black complainants only)
    counts_per_officer = [len(complaints) for complaints in officer_to_complaints.values()]

    # 90th percentile of complaint counts per officer
    sorted_counts = sorted(counts_per_officer)
    index_90 = max(0, math.ceil(0.9 * len(sorted_counts)) - 1)
    p90_value = sorted_counts[index_90]

    officers_above_p90 = {
        mos_id
        for mos_id, complaints in officers_sorted
        if len(complaints) > p90_value
    }

    complaints_from_above_p90: set[str] = set()
    for mos_id in officers_above_p90:
        complaints_from_above_p90.update(officer_to_complaints[mos_id])

    remaining_black_complaints_p90 = len(
        all_black_complaints - complaints_from_above_p90
    )

    complaints_from_top_officers: set[str] = set()
    for mos_id in top_officers:
        complaints_from_top_officers.update(officer_to_complaints[mos_id])

    remaining_black_complaints = len(all_black_complaints - complaints_from_top_officers)

    print(f"Total complaints from Black complainants: {total_black_complaints}")
    print(
        "Total complaints from Black complainants after removing "
        f"top 10% officers by Black-complainant complaints: {remaining_black_complaints}"
    )
    print(
        f"90th percentile complaint count per officer: {p90_value}"
    )
    print(
        "Total complaints from Black complainants after removing officers above the "
        f"90th-percentile complaint count: {remaining_black_complaints_p90}"
    )
    print(
        f"Number of officers removed using percentile rule: {len(officers_above_p90)}"
    )

    # Per-year ratios before/after removing top 10% officers (by year)
    year_ratios: list[tuple[str, float, int, int]] = []
    sum_black_all_years = 0
    sum_black_after_per_year_removal = 0

    for year in sorted(year_all_black_complaints.keys()):
        complaints_set = year_all_black_complaints[year]
        total_year_black = len(complaints_set)
        if total_year_black == 0:
            continue

        year_officer_map = year_officer_to_complaints[year]
        if not year_officer_map:
            continue

        year_officers_sorted = sorted(
            year_officer_map.items(), key=lambda kv: len(kv[1]), reverse=True
        )
        num_year_officers = len(year_officers_sorted)
        top_year_count = max(1, math.ceil(num_year_officers * 0.10))
        top_year_officers = {
            mos_id for mos_id, _ in year_officers_sorted[:top_year_count]
        }

        complaints_from_top_year_officers: set[str] = set()
        for mos_id in top_year_officers:
            complaints_from_top_year_officers.update(year_officer_map[mos_id])

        remaining_year_black = len(complaints_set - complaints_from_top_year_officers)
        ratio = total_year_black / max(remaining_year_black, 1)
        year_ratios.append((year, ratio, total_year_black, remaining_year_black))

        sum_black_all_years += total_year_black
        sum_black_after_per_year_removal += remaining_year_black

    # Compare sum of Black complaints over all years: with vs without per-year top-10% removal
    print("\n--- Sum of Black complaints over all years ---")
    print(f"Total (no removal): {sum_black_all_years}")
    print(
        "Total after removing top 10% of officers in each year: "
        f"{sum_black_after_per_year_removal}"
    )
    if sum_black_all_years:
        reduction = 1 - sum_black_after_per_year_removal / sum_black_all_years
        print(f"Reduction from per-year top-10% removal: {reduction:.1%}")
    print()

    print(year_ratios)
    year_ratios.sort(key=lambda x: x[1])  # ascending: biggest impact first
    top_years = year_ratios[:5]

    if top_years:
        print("\nTop 5 years by reduction ratio (after/before) when removing top 10% officers:")
        for year, ratio, total_year_black, remaining_year_black in top_years:
            print(
                f"  Year {year}: ratio={ratio:.3f} "
                f"(before={total_year_black}, after={remaining_year_black})"
            )

    # Show counts for officers in the top 10%
    top_officer_counts = [
        (mos_id, len(officer_to_complaints[mos_id])) for mos_id in top_officers
    ]
    top_officer_counts.sort(key=lambda x: x[1], reverse=True)
    print(f"\nTop {top_count} officers by Black-complainant complaints:")
    for mos_id, count in top_officer_counts:
        print(f"  Officer {mos_id}: {count} complaints from Black complainants")

    # Histogram: x = complaints from Black complainants per officer,
    # y = frequency, stacked by complaints from White vs Black complainants.
    # For each officer, compute the number of complaints from Black and White complainants.
    freq_black_counts: dict[int, int] = defaultdict(int)
    freq_white_counts: dict[int, int] = defaultdict(int)

    for mos_id, by_race in officer_complaints_by_race.items():
        black_count = len(by_race.get("Black", set()))
        white_count = len(by_race.get("White", set()))
        freq_black_counts[black_count] += 1
        freq_white_counts[white_count] += 1

    if freq_black_counts or freq_white_counts:
        xs = sorted(set(freq_black_counts.keys()) | set(freq_white_counts.keys()))
        black_vals = [freq_black_counts.get(x, 0) for x in xs]
        white_vals = [freq_white_counts.get(x, 0) for x in xs]

        sns.set_theme(style="whitegrid")
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.bar(xs, black_vals, label="Black complainants")
        ax.bar(xs, white_vals, bottom=black_vals, label="White complainants")

        ax.set_xlabel("Number of complaints per officer")
        ax.set_ylabel("Frequency (number of officers)")
        ax.set_title(
            "Complaint-count distribution per officer\n"
            "Stacked by complainant race (Black vs White)"
        )
        ax.legend()
        plt.tight_layout()
        out_path = Path(__file__).with_name("black_white_complaint_count_distribution.png")
        plt.savefig(out_path, dpi=150)
        plt.show()
        print(f"Stacked complaint-count distribution saved to {out_path}")


if __name__ == "__main__":
    main()

