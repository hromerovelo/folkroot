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
  Main script for segment clustering using Quality Threshold Clustering algorithm.

  This script reads segment alignment data from the SQLite database and clusters
  segments based on a specified feature type (e.g., diatonic, chromatic, rhythmic).
  The Quality Threshold Clustering (QTC) algorithm is used to group segments based
  on a distance threshold, which can be specified directly or calculated from a
  percentile value.
    
  The script generates detailed DataFrames with segment and cluster information,
  saves the results to Excel files, and optionally creates a cluster visualization
  and individual PDF files for each cluster.
    
  Usage:
    python qt_segments_clustering.py -f <feature> [-t <threshold>] [-p <percentile>] [-v]
"""

import argparse
from collections import defaultdict
import numpy as np
import os
import sqlite3
import sys

# Local imports
from segments_utils.clustering_excel_files_generation import (
    create_segments_dataframe,
    create_clusters_dataframe,
    save_results_to_excel,
)
from segments_utils.clustering_visualization import (
    calculate_cluster_distances,
    create_cluster_visualization,
    create_cluster_pdfs,
)

# Set random seeds for reproducibility
np.random.seed(42)


def can_merge_clusters(
    cursor, cluster1_elements, cluster2_elements, score_column, threshold
):
    """
    Check if all elements between two clusters are within threshold distance.

    Args:
        cursor: SQLite cursor for database operations
        cluster1_elements (set): Elements from first cluster
        cluster2_elements (set): Elements from second cluster
        score_column (str): Score column name
        threshold (float): Maximum allowed distance

    Returns:
        bool: True if all elements are within threshold distance
    """
    placeholders = ",".join(["?" for _ in cluster2_elements])
    cursor.execute(
        f"""
        SELECT COUNT(*) 
        FROM segmentalignment 
        WHERE segment_id_1 IN ({','.join(['?' for _ in cluster1_elements])})
        AND segment_id_2 IN ({placeholders})
        AND {score_column} > ?
    """,
        list(cluster1_elements) + list(cluster2_elements) + [threshold],
    )

    return cursor.fetchone()[0] == 0


def cluster_with_qtc(cursor, threshold, feature):
    """
    Clusters elements using Quality Threshold Clustering (QTC).
    Ensures all segments are assigned to a cluster, even as single-element clusters.

    Args:
        cursor: SQLite cursor for database operations
        threshold (float): Maximum distance threshold for clustering
        feature (str): Feature type for clustering

    Returns:
        dict: Dictionary mapping segment IDs to cluster IDs
    """
    score_column = f"{feature}_score"

    # Get ALL segments from Segment table - this is our source of truth
    cursor.execute("SELECT segment_id FROM Segment")
    all_segments = {row[0] for row in cursor.fetchall()}

    # Get all segments with zero distance
    cursor.execute(
        f"""
        SELECT segment_id_1, segment_id_2 
        FROM segmentalignment 
        WHERE {score_column} = 0
    """
    )

    # Build initial clusters of identical elements
    zero_distance_pairs = cursor.fetchall()
    initial_clusters = defaultdict(set)

    for id1, id2 in zero_distance_pairs:
        initial_clusters[id1].add(id1)
        initial_clusters[id1].add(id2)
        if id2 in initial_clusters:
            initial_clusters[id1].update(initial_clusters[id2])
            for elem in initial_clusters[id2]:
                initial_clusters[elem] = initial_clusters[id1]

    # Convert to regular clusters with IDs
    clusters = {}
    cluster_id = 0
    processed = set()

    for elements in initial_clusters.values():
        if not elements & processed:
            for element in elements:
                clusters[element] = cluster_id
            processed.update(elements)
            cluster_id += 1

    # Get remaining unprocessed segments
    remaining = all_segments - processed

    # Process remaining elements
    while remaining:
        current = remaining.pop()
        if current not in clusters:
            cursor.execute(
                f"""
                SELECT segment_id_2 
                FROM segmentalignment 
                WHERE segment_id_1 = ? 
                AND {score_column} <= ?
            """,
                (current, threshold),
            )

            neighbors = {row[0] for row in cursor.fetchall()}
            current_cluster = {current}

            for neighbor in neighbors:
                if neighbor in clusters:
                    # Try to merge with existing cluster
                    neighbor_cluster = {
                        k for k, v in clusters.items() if v == clusters[neighbor]
                    }
                    if can_merge_clusters(
                        cursor,
                        current_cluster,
                        neighbor_cluster,
                        score_column,
                        threshold,
                    ):
                        clusters[current] = clusters[neighbor]
                        break
                elif neighbor in remaining:
                    # Add to current cluster if compatible
                    if can_merge_clusters(
                        cursor, current_cluster, {neighbor}, score_column, threshold
                    ):
                        current_cluster.add(neighbor)
                        remaining.remove(neighbor)

            # Create new cluster if not merged
            if current not in clusters:
                new_cluster_id = max(clusters.values(), default=-1) + 1
                for element in current_cluster:
                    clusters[element] = new_cluster_id

    # Get segments that are not yet in any cluster
    unassigned = all_segments - set(clusters.keys())

    # Assign each unassigned segment to its own cluster
    for segment in unassigned:
        new_cluster_id = max(clusters.values(), default=-1) + 1
        clusters[segment] = new_cluster_id

    # Verify all segments are assigned
    assert len(clusters) == len(
        all_segments
    ), "Some segments were not assigned to clusters"

    return clusters


def verify_clustering(cursor, clusters):
    """
    Verify that all segments in the database have been assigned to a cluster.

    Args:
        cursor: SQLite cursor for database operations
        clusters (dict): Dictionary mapping segment IDs to cluster IDs

    Returns:
        bool: True if all segments are assigned to clusters
    """
    # Get all segments from database
    cursor.execute("SELECT COUNT(*) FROM Segment")
    total_segments = cursor.fetchone()[0]

    # Check numbers
    segments_in_clusters = len(clusters)
    unique_clusters = len(set(clusters.values()))

    print("\nClustering verification:")
    print(f"- Total segments in database: {total_segments}")
    print(f"- Segments assigned to clusters: {segments_in_clusters}")
    print(f"- Number of unique clusters: {unique_clusters}")

    # Get any unassigned segments
    cursor.execute(
        """
        SELECT segment_id 
        FROM Segment 
        WHERE segment_id NOT IN ({})
    """.format(
            ",".join(map(str, clusters.keys()))
        )
    )

    unassigned = cursor.fetchall()
    if unassigned:
        print("\nWARNING: Found unassigned segments:")
        for (sid,) in unassigned:
            print(f"- Segment ID: {sid}")

    return len(unassigned) == 0


def get_score_percentile(cursor, feature, percentile):
    """
    Get the score value at the specified percentile from the database.

    Args:
        cursor: SQLite cursor for database operations
        feature: Feature type for score calculation
        percentile: Percentile value (0-100)

    Returns:
        float: Score value at the specified percentile
    """
    score_column = f"{feature}_score"
    cursor.execute(
        f"""
        SELECT {score_column}
        FROM segmentalignment
        WHERE {score_column} IS NOT NULL
        ORDER BY {score_column}
    """
    )

    # Get all scores
    scores = [row[0] for row in cursor.fetchall()]

    if not scores:
        raise ValueError(f"No scores found for feature {feature}")

    # Calculate the exact percentile using numpy
    return float(np.percentile(scores, percentile))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cluster segments using QT Clustering")
    parser.add_argument(
        "-f",
        "--feature",
        type=str,
        required=True,
        choices=[
            "diatonic",
            "chromatic",
            "rhythmic",
            "diatonic_rhythmic",
            "chromatic_rhythmic",
        ],
        help="Feature type for clustering",
    )
    parser.add_argument(
        "-t",
        "--threshold",
        type=float,
        required=False,
        help="Distance threshold for clustering (e.g., 5.0 for 5%% difference)",
    )
    parser.add_argument(
        "-p",
        "--percentile",
        type=int,
        default=10,
        choices=range(1, 100),
        help="Percentile to use as threshold (1-99, default: 10)",
        metavar="P",
    )
    parser.add_argument(
        "-v",
        "--visualize",
        action="store_true",
        help="Create cluster visualization.",
    )
    parser.add_argument(
        "-pdf",
        "--pdf",
        action="store_true",
        help="Create PDF files for each cluster.",
    )

    args = parser.parse_args()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.abspath(os.path.join(script_dir, "../database/folkroot.db"))
    output_dir = os.path.join(script_dir, f"results/{args.feature}_clustering")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Determine threshold
    threshold = args.threshold
    if threshold is None:
        threshold = get_score_percentile(cursor, args.feature, args.percentile)
        print(f"Using {args.percentile}th percentile as threshold: {threshold:.2f}")

    print(
        f"Starting clustering process with {args.feature} feature (threshold: {threshold})..."
    )
    clusters = cluster_with_qtc(cursor, threshold, args.feature)
    total_clusters = len(set(clusters.values()))
    print(f"\nFound {len(clusters)} segments in {total_clusters} clusters")

    print("Creating detailed DataFrames...")
    segments_df = create_segments_dataframe(cursor, clusters)
    clusters_df = create_clusters_dataframe(cursor, clusters)
    print(f"Created segments summary with {len(segments_df)} rows")

    # Calculate some basic statistics
    single_element_clusters = sum(
        1 for _, row in clusters_df.iterrows() if row["total_segments"] == 1
    )
    largest_cluster_size = clusters_df["total_segments"].max()

    print(f"Clustering statistics:")
    print(f"- Total clusters: {total_clusters}")
    print(f"- Single-element clusters: {single_element_clusters}")
    print(f"- Largest cluster size: {largest_cluster_size}")

    print("Saving results to Excel files...")
    save_results_to_excel(segments_df, clusters_df, output_dir, args.feature)
    print(f"Results saved to Excel files in {output_dir}")

    if args.visualize:
        print("Creating cluster visualization...")
        cluster_info = calculate_cluster_distances(
            cursor, clusters, f"{args.feature}_score"
        )
        create_cluster_visualization(
            clusters_df, cluster_info, output_dir, args.feature
        )
        print(f"Cluster visualization saved to HTML file in {output_dir}")

    if args.pdf:
        print("Creating cluster PDFs...")
        create_cluster_pdfs(clusters_df, output_dir, args.feature, cursor, script_dir)

    print("\nVerifying clustering results...")
    if not verify_clustering(cursor, clusters):
        print("ERROR: Not all segments were assigned to clusters!")
        sys.exit(1)

    conn.close()
