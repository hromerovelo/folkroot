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
  Created by Hilda Romero-Velo on March 2025.
"""


"""Analyze and visualize the distribution of distances for each feature in SegmentAlignment."""

import sqlite3
import os
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import numpy as np


def analyze_feature_distributions(db_path, output_dir):
    """
    Analyze and plot the distribution of scores for each feature,
    highlighting the 10th percentile (P10) as a potential threshold.

    Args:
        db_path: Path to SQLite database
        output_dir: Directory to save plots and statistics
    """
    conn = sqlite3.connect(db_path)

    features = [
        "diatonic_score",
        "chromatic_score",
        "rhythmic_score",
        "diatonic_rhythmic_score",
        "chromatic_rhythmic_score",
    ]

    features_titles = [
        "Diatonic",
        "Chromatic",
        "Rhythmic",
        "Diatonic Rhythmic",
        "Chromatic Rhythmic",
    ]

    # Create combined figure
    fig_combined, axes = plt.subplots(
        1, len(features_titles), figsize=(5 * len(features), 6)
    )
    fig_combined.suptitle("Distribution of Segments Alignment Distances", fontsize=16)

    stats = []
    for i, (feature, title) in enumerate(zip(features, features_titles)):
        # Get data for this feature
        query = f"SELECT {feature} FROM SegmentAlignment WHERE {feature} IS NOT NULL"
        df = pd.read_sql_query(query, conn)

        # Calculate key statistics
        desc = df[feature].describe()
        q1, q3 = desc["25%"], desc["75%"]
        iqr = q3 - q1

        # Compute thresholds
        threshold_p10 = np.percentile(df[feature], 10)
        threshold_iqr = max(0, q1 - 1.5 * iqr)  # Avoid negative thresholds

        # Store statistics
        stats.append(
            {
                "Feature": feature,
                "Count": desc["count"],
                "Mean": desc["mean"],
                "Std": desc["std"],
                "Min": desc["min"],
                "Q1": q1,
                "Median": desc["50%"],
                "Q3": q3,
                "Max": desc["max"],
                "Threshold_IQR": threshold_iqr,
                "Threshold_P10": threshold_p10,
            }
        )

        # Plot in combined figure
        plot_feature_distribution(
            df[feature], desc, q1, q3, threshold_p10, threshold_iqr, axes[i], title
        )

        # Create individual figure
        fig_individual, ax_individual = plt.subplots(figsize=(10, 6))
        plot_feature_distribution(
            df[feature],
            desc,
            q1,
            q3,
            threshold_p10,
            threshold_iqr,
            ax_individual,
            title,
        )

        # Save individual figure
        plt.tight_layout()
        fig_individual.savefig(
            os.path.join(output_dir, f"distribution_{feature}.png"),
            bbox_inches="tight",
            dpi=300,
        )
        plt.close(fig_individual)

    # Save combined figure
    plt.tight_layout(rect=[0, 0, 0.95, 0.95])
    fig_combined.savefig(
        os.path.join(output_dir, "segments_distances_distributions.png"),
        bbox_inches="tight",
        dpi=300,
    )
    plt.close(fig_combined)

    # Save statistics to CSV
    stats_df = pd.DataFrame(stats)
    stats_df.to_csv(
        os.path.join(output_dir, "segments_distances_statistics.csv"), index=False
    )

    print("\nSegments Distances Distribution Statistics:")
    print(stats_df.to_string(index=False))

    conn.close()


def plot_feature_distribution(
    data, desc, q1, q3, threshold_p10, threshold_iqr, ax, title
):
    """
    Helper function to create distribution plot with statistics.

    Args:
        data: Feature data to plot
        desc: Descriptive statistics
        q1, q3: First and third quartiles
        threshold_p10: 10th percentile threshold
        threshold_iqr: IQR-based threshold
        ax: Matplotlib axis to plot on
        title: Plot title
    """
    sns.histplot(
        data=data, ax=ax, bins=50, color="royalblue", alpha=0.6, label="Distribution"
    )

    # Add vertical lines for all statistics
    statistics = [
        (desc["mean"], "red", "Mean"),
        (desc["50%"], "green", "Median"),
        (q1, "orange", "Q1"),
        (q3, "orange", "Q3"),
        (threshold_p10, "blue", "P10"),
        (threshold_iqr, "purple", "IQR"),
    ]

    for value, color, label in statistics:
        ax.axvline(
            x=value,
            color=color,
            linestyle="--",
            linewidth=2,
            label=f"{label} = {int(value)}",
            alpha=0.8,
        )

    ax.set_title(title)
    ax.set_xlabel("Distance")
    ax.set_ylabel("Count")
    ax.legend(bbox_to_anchor=(1.05, 1), loc="upper left")


if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.abspath(os.path.join(script_dir, "../database/folkroot.db"))
    output_dir = os.path.join(script_dir, "results/segments_distances_distribution")

    os.makedirs(output_dir, exist_ok=True)
    analyze_feature_distributions(db_path, output_dir)
