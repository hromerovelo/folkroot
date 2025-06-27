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

"""
  Script to analyze clustering results and generate visualizations.
"""

import os
import pandas as pd
import matplotlib
import sqlite3

matplotlib.use("Agg")  # Set backend before importing pyplot
import matplotlib.pyplot as plt
import numpy as np


def get_clusters_with_different_scores(db_path, df):
    """
    Filter clusters that contain segments from different scores.

    Args:
        db_path (str): Path to the SQLite database
        df (pd.DataFrame): DataFrame with clustering results

    Returns:
        set: Set of cluster IDs that have segments from different scores
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    diverse_clusters = set()

    for cluster_id in df["cluster_id"].unique():
        # Get segments in this cluster
        segments = df[df["cluster_id"] == cluster_id]["segment_id"].tolist()

        # Query to get unique scores for these segments
        cursor.execute(
            """
            SELECT COUNT(DISTINCT s.score_id)
            FROM Segment seg
            JOIN Score s ON seg.score_id = s.score_id
            WHERE seg.segment_id IN ({})
        """.format(
                ",".join("?" * len(segments))
            ),
            segments,
        )

        unique_scores = cursor.fetchone()[0]

        # If more than one score, add to diverse clusters
        if unique_scores > 1:
            diverse_clusters.add(cluster_id)

    conn.close()
    return diverse_clusters


def create_cluster_dataset_distribution(excel_file, output_dir, db_path, feature):
    """
    Create a grouped bar plot showing the distribution of datasets across clusters.

    Args:
        excel_file (str): Path to the Excel file with segment clustering results
        output_dir (str): Directory to save the plot
        feature (str): Feature type used for clustering
    """
    df = pd.read_excel(excel_file)

    # Filter clusters with segments from different scores
    diverse_clusters = get_clusters_with_different_scores(db_path, df)

    # Filter DataFrame to keep only diverse clusters
    df_filtered = df[df["cluster_id"].isin(diverse_clusters)]

    cluster_dataset = pd.crosstab(df_filtered["cluster_id"], df_filtered["dataset"])

    # Sort clusters by total size (descending)
    cluster_dataset["total"] = cluster_dataset.sum(axis=1)
    cluster_dataset = cluster_dataset.sort_values("total", ascending=False)
    cluster_dataset = cluster_dataset.drop("total", axis=1)

    # Calculate figure size based on number of clusters
    num_clusters = len(cluster_dataset)

    if num_clusters == 0:
        print(f"\nNo clusters with segments from different scores found for {feature}")
        return None

    fig_width = max(12, num_clusters * 0.5)

    plt.figure(figsize=(fig_width, 10), dpi=300)

    # Create stacked bar plot
    x = np.arange(len(cluster_dataset.index))
    bottom_bars = plt.bar(x, cluster_dataset["irish"], label="Irish", color="#2ecc71")
    top_bars = plt.bar(
        x,
        cluster_dataset["galician"],
        bottom=cluster_dataset["irish"],
        label="Galician",
        color="#3498db",
    )

    # Add value labels for Irish segments (optional)
    for i, v in enumerate(cluster_dataset["irish"]):
        if v > 0:  # Only show if there are Irish segments
            plt.text(
                x[i],
                v / 2,
                str(int(v)),
                ha="center",
                va="center",
                fontsize=8 if num_clusters > 30 else 10,
                color="white",
            )

    # Add value labels for Galician segments (optional)
    for i, v in enumerate(cluster_dataset["galician"]):
        if v > 0:  # Only show if there are Galician segments
            plt.text(
                x[i],
                cluster_dataset["irish"].iloc[i] + v / 2,
                str(int(v)),
                ha="center",
                va="center",
                fontsize=8 if num_clusters > 30 else 10,
                color="white",
            )

    # Add total labels at the top of each stacked bar
    totals = cluster_dataset.sum(axis=1)
    for i, total in enumerate(totals):
        plt.text(
            x[i],
            total + 0.5,
            f"{int(total)}",
            ha="center",
            va="bottom",
            fontsize=8 if num_clusters > 30 else 10,
        )

    plt.title(
        f"Segment Distribution per Cluster - {feature.capitalize()} Features",
        pad=20,
        fontsize=14,
    )
    plt.xlabel("Cluster ID", labelpad=10)
    plt.ylabel("Number of Segments", labelpad=10)

    if num_clusters > 30:
        plt.xticks(x, cluster_dataset.index, rotation=90, fontsize=8)
    else:
        plt.xticks(x, cluster_dataset.index, rotation=45)

    plt.legend(title="Dataset")
    plt.grid(True, axis="y", linestyle="--", alpha=0.7)
    plt.tight_layout()
    output_file = os.path.join(output_dir, f"cluster_distribution_{feature}.pdf")
    plt.savefig(output_file, format="pdf", bbox_inches="tight", dpi=300)
    plt.close()

    total_segments = df_filtered.shape[0]
    total_clusters = df_filtered["cluster_id"].nunique()
    irish_segments = df_filtered[df_filtered["dataset"] == "irish"].shape[0]
    galician_segments = df_filtered[df_filtered["dataset"] == "galician"].shape[0]
    filtered_clusters = len(df["cluster_id"].unique()) - total_clusters

    print("\nClustering Analysis Results:")
    print(f"Total number of segments (in diverse clusters): {total_segments}")
    print(f"Total number of diverse clusters: {total_clusters}")
    print(f"Clusters filtered (single score): {filtered_clusters}")
    print(f"Irish segments: {irish_segments}")
    print(f"Galician segments: {galician_segments}")

    return cluster_dataset


if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.abspath(os.path.join(script_dir, "../database/folkroot.db"))

    features = [
        "diatonic",
        "chromatic",
        "rhythmic",
        "diatonic_rhythmic",
        "chromatic_rhythmic",
    ]

    for feature in features:
        results_dir = os.path.join(script_dir, f"results/{feature}_clustering")
        excel_file = os.path.join(results_dir, f"segments_clustering_{feature}.xlsx")

        if os.path.exists(excel_file):
            print(f"\nAnalyzing {feature} clustering results...")
            cluster_dataset = create_cluster_dataset_distribution(
                excel_file, results_dir, db_path, feature
            )
            if cluster_dataset is not None:
                print(f"Plot saved in: {results_dir}")
            else:
                print(f"No visualization generated for {feature}")
        else:
            print(f"Warning: No results found for {feature} clustering")
