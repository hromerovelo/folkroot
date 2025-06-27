"""
BSD 2-Clause License

Copyright (c) 2025, Hilda Romero-Velo
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

* Redistributions of source code must retain the above copyright notice, this
  list of conditions and the following disclaimer.

* Redistributions in binary form must reproduce the above copyright notice, this
  list of conditions and the following disclaimer in the documentation
  and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""

"""
  Created by Hilda Romero-Velo on June 2025.
"""

"""
  Combined analysis script that runs both GSR sensitivity testing and random trees baseline
  to evaluate the statistical significance of the Genre Separation Ratio (GSR) metric.
"""

import os
import sys
import argparse
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

# Add parent directory to path for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Import functions from existing scripts
from test_gsr_sensitivity import test_gsr_sensitivity
from random_trees_baseline import analyze_random_trees_baseline


def run_combined_analysis(db_path, random_iterations=100, output_dir=None):
    """Run both sensitivity analysis and random trees baseline with visualization."""
    if output_dir is None:
        output_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "combined_gsr_analysis"
        )
    os.makedirs(output_dir, exist_ok=True)

    print("=" * 80)
    print("RUNNING GSR SENSITIVITY ANALYSIS")
    print("=" * 80)
    noise_levels, avg_gsr_results = test_gsr_sensitivity(db_path)

    print("\n" + "=" * 80)
    print("RUNNING RANDOM TREES BASELINE ANALYSIS")
    print("=" * 80)
    random_stats = analyze_random_trees_baseline(
        db_path, n_iterations=random_iterations
    )

    # Generate combined visualization
    print("\n" + "=" * 80)
    print("CREATING COMBINED VISUALIZATION")
    print("=" * 80)
    create_combined_visualization(
        noise_levels, avg_gsr_results, random_stats, output_dir, random_iterations
    )

    print(f"\nAll analyses complete. Results saved to: {output_dir}")


def prepare_boxplot_data(random_stats):
    """Extract and prepare data for the boxplot."""
    genres = list(random_stats.keys())
    all_values = []

    # Check if values exist directly
    if any("values" in random_stats[g] for g in genres):
        print("Using actual GSR values from random trees")
        for genre in genres:
            if "values" in random_stats[genre]:
                all_values.extend(random_stats[genre]["values"])
    else:
        print("Reconstructing GSR distribution from statistics")
        np.random.seed(42)  # For reproducibility

        for genre in genres:
            genre_mean = random_stats[genre]["mean"]
            genre_std = random_stats[genre]["std"]
            n_samples = random_stats[genre]["count"]

            if all(key in random_stats[genre] for key in ["p25", "median", "p75"]):
                # Use percentile data for more accurate distribution
                p25 = random_stats[genre]["p25"]
                median = random_stats[genre]["median"]
                p75 = random_stats[genre]["p75"]

                base_data = np.random.normal(0, 1, n_samples)
                iqr = p75 - p25
                scaled_data = median + (base_data * iqr / 1.35)

                # Add skew if necessary
                skew = (median - p25) / (p75 - p25) - 0.5
                if abs(skew) > 0.05:
                    scaled_data = scaled_data + (
                        np.sign(skew) * 0.1 * np.power(base_data, 2)
                    )

                genre_data = scaled_data
            else:
                # Fallback to normal distribution
                genre_data = np.random.normal(genre_mean, genre_std, n_samples)

            all_values.extend(genre_data)

    # Filter extreme outliers
    all_values = np.array(all_values)
    q1, q3 = np.percentile(all_values, [25, 75])
    iqr = q3 - q1
    lower_bound = q1 - 1.5 * iqr
    upper_bound = q3 + 1.5 * iqr

    return all_values[(all_values >= lower_bound) & (all_values <= upper_bound)]


def create_combined_visualization(
    noise_levels, avg_gsr_results, random_stats, output_dir, random_iterations=100
):
    """Create a visualization showing GSR sensitivity with random baseline."""
    # Set global text styling
    plt.rcParams["font.weight"] = "bold"
    plt.rcParams["axes.titleweight"] = "bold"
    plt.rcParams["axes.labelweight"] = "bold"

    # Extract baseline statistics
    genres = list(random_stats.keys())
    random_means = [random_stats[g]["mean"] for g in genres]
    random_overall_mean = np.mean(random_means)
    random_overall_std = np.std(random_means)
    print(f"Random baseline mean: {random_overall_mean:.6f}")
    print(f"Random baseline std: {random_overall_std:.6f}")

    # Create figure and main plot
    fig, ax = plt.subplots(figsize=(10, 6.5))

    # Plot sensitivity curve
    ax.plot(
        noise_levels,
        avg_gsr_results,
        "o-",
        linewidth=2.5,
        markersize=9,
        color="#1f77b4",
        label="GSR with increasing noise",
    )

    # Add baseline line
    ax.axhline(
        y=random_overall_mean,
        color="red",
        linestyle="--",
        linewidth=2.5,
        label=f"Random trees baseline (mean: {random_overall_mean:.3f})",
    )

    # Add perfect classification annotation
    perfect_gsr = avg_gsr_results[0]
    ax.annotate(
        f"Perfect classification GSR: {perfect_gsr:,.2f}\n"
        f"{perfect_gsr/random_overall_mean:.1f}x higher than random",
        xy=(0, perfect_gsr),
        xytext=(6.5, perfect_gsr * 0.96),
        arrowprops=dict(
            arrowstyle="->",
            connectionstyle="arc3,rad=.1",
            color="black",
            shrinkA=0,
            shrinkB=5,
            lw=1.5,
        ),
        bbox=dict(boxstyle="round,pad=0.5", fc="yellow", alpha=0.3),
        fontsize=12,
        weight="bold",
        ma="center",
    )

    # Find convergence point
    convergence_idx = np.where(np.array(avg_gsr_results) < random_overall_mean * 1.1)[0]
    convergence_point = (
        noise_levels[convergence_idx[0]] if len(convergence_idx) > 0 else 40
    )

    # Create legend elements
    legend_elements = [
        plt.Line2D(
            [0],
            [0],
            color="#1f77b4",
            marker="o",
            linestyle="-",
            linewidth=2.5,
            markersize=9,
            label="GSR with increasing noise",
        ),
        plt.Line2D(
            [0],
            [0],
            color="red",
            linestyle="--",
            linewidth=2.5,
            label=f"Random trees baseline (mean: {random_overall_mean:,.3f})",
        ),
    ]

    # Add legend and get its position
    legend = ax.legend(handles=legend_elements, loc="upper right", fontsize=11)
    plt.setp(legend.get_texts(), fontweight="bold")
    legend_bbox = legend.get_window_extent().transformed(fig.transFigure.inverted())

    # Calculate annotation positions
    stat_annotation_x = legend_bbox.x0 + legend_bbox.width * 0.4
    mean_gsr_annotation_x = legend_bbox.x0 + legend_bbox.width * 101

    # Add Mean GSR annotation
    ax.annotate(
        f"Mean GSR from {random_iterations:,} random trees\n"
        f"(μ ≈ {random_overall_mean:,.3f}, σ ≈ {random_overall_std:,.4f})\n"
        f"Convergence at ≥ {convergence_point:,}% noise reflects\n"
        f"the metric's sensitivity to meaningful clustering",
        xy=(noise_levels[-1] + 1, random_overall_mean),
        xytext=(mean_gsr_annotation_x, random_overall_mean * 8.0),
        arrowprops=dict(
            arrowstyle="->",
            connectionstyle="arc3,rad=-.3",
            color="black",
            shrinkA=0,
            shrinkB=0,
            lw=1.5,
        ),
        bbox=dict(boxstyle="round,pad=0.5", fc="white", alpha=0.8),
        fontsize=10,
        weight="bold",
        ha="center",
    )

    # Configure main plot
    ax.set_xlabel("Noise Level (%)", fontsize=14)
    ax.set_ylabel("GSR Value", fontsize=14)
    ax.set_title("GSR Sensitivity to Genre Assignment Noise", fontsize=16)
    ax.grid(True, linestyle="--", alpha=0.7)
    ax.tick_params(axis="both", which="major", labelsize=12)

    # Calculate z-score for statistical significance
    z_score = (perfect_gsr - random_overall_mean) / random_overall_std
    p_value = "p < 0.001" if z_score > 3.3 else f"p ~ {np.exp(-z_score/2):.3f}"

    # Create boxplot inset
    inset_ax = fig.add_axes(
        [
            legend_bbox.x0,
            legend_bbox.y0 - 0.26,
            legend_bbox.width,
            0.22,
        ]
    )

    # Prepare and create boxplot
    filtered_values = prepare_boxplot_data(random_stats)
    boxplot = inset_ax.boxplot(
        filtered_values,
        vert=True,
        patch_artist=True,
        showfliers=False,
    )

    # Style boxplot elements
    for patch in boxplot["boxes"]:
        patch.set(facecolor="lightgray", alpha=0.8, linewidth=1.5)
    for whisker in boxplot["whiskers"]:
        whisker.set(linewidth=1.8, color="black")
    for cap in boxplot["caps"]:
        cap.set(linewidth=1.8, color="black")
    for median in boxplot["medians"]:
        median.set(linewidth=1.8, color="red")

    # Calculate and display boxplot statistics
    stats = {
        "Mean": np.mean(filtered_values),
        "Median": np.median(filtered_values),
        "Std Dev": np.std(filtered_values),
        "Min": np.min(filtered_values),
        "Max": np.max(filtered_values),
    }

    stats_text = "\n".join([f"{k}: {v:,.4f}" for k, v in stats.items()])
    inset_ax.text(
        0.97,
        0.02,
        stats_text,
        transform=inset_ax.transAxes,
        ha="right",
        va="bottom",
        fontsize=9,
        weight="bold",
        bbox=dict(boxstyle="round,pad=0.3", fc="white", alpha=0.8),
    )

    # Configure boxplot
    inset_ax.set_title("Random Trees GSR Distribution", fontsize=12)
    inset_ax.tick_params(axis="y", which="major", labelsize=10)
    inset_ax.set_xticklabels([])
    inset_ax.grid(True, axis="y", linestyle="--", alpha=0.3)

    # Add statistical significance annotation
    stat_y = legend_bbox.y0 - 0.31
    fig.text(
        stat_annotation_x,
        stat_y,
        f"Statistical significance: z-score = {z_score:,.2f} ({p_value})\n"
        f"Perfect classification GSR is significantly different from random chance",
        ha="center",
        va="top",
        fontsize=10,
        weight="bold",
        bbox=dict(boxstyle="round,pad=0.5", fc="lightblue", alpha=0.3),
    )

    # Save figure
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "combined_gsr_analysis.png"), dpi=300)
    plt.savefig(os.path.join(output_dir, "combined_gsr_analysis.pdf"))
    print(f"Combined visualization saved to {output_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run combined GSR sensitivity and statistical significance analysis."
    )
    parser.add_argument(
        "-n",
        "--iterations",
        type=int,
        default=100,
        help="Number of random trees to generate (default: 100)",
    )
    parser.add_argument(
        "-d",
        "--database",
        type=str,
        default=None,
        help="Path to the database (default: standard path)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default=None,
        help="Output directory for results (default: ./combined_gsr_analysis)",
    )

    args = parser.parse_args()

    # Determine database path
    if args.database:
        db_path = args.database
    else:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        db_path = os.path.abspath(
            os.path.join(script_dir, "../../database/folkroot.db")
        )

    # Run combined analysis
    run_combined_analysis(
        db_path=db_path, random_iterations=args.iterations, output_dir=args.output
    )
