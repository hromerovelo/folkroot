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

"""Functions for creating and exporting DataFrames to Excel files."""

import os
import pandas as pd


def create_segments_dataframe(cursor, clusters):
    """
    Create DataFrame with segment details including cluster assignments.
    Ensures all segments are included, even those in single-element clusters.

    Args:
        cursor: SQLite cursor
        clusters: Dictionary mapping segment_ids to cluster_ids

    Returns:
        pandas.DataFrame: DataFrame with segment details
    """
    segment_ids = list(clusters.keys())
    placeholders = ",".join("?" * len(segment_ids))

    cursor.execute(
        f"""
        SELECT sg.segment_id, sc.genre, sc.dataset
        FROM Segment sg
        JOIN Score sc ON sg.score_id = sc.score_id
        WHERE sg.segment_id IN ({placeholders})
        ORDER BY sg.segment_id
    """,
        segment_ids,
    )

    segments_data = []
    for segment_id, genre, dataset in cursor.fetchall():
        segments_data.append(
            {
                "segment_id": segment_id,
                "cluster_id": clusters[segment_id],
                "genre": genre,
                "dataset": dataset,
            }
        )

    return pd.DataFrame(segments_data)


def create_clusters_dataframe(cursor, clusters):
    """
    Create DataFrame with cluster details and segment notations.
    Ensures all clusters are included, including single-element ones.

    Args:
        cursor: SQLite cursor
        clusters: Dictionary mapping segment_ids to cluster_ids

    Returns:
        pandas.DataFrame: DataFrame with cluster details
    """
    clusters_data = []
    all_cluster_ids = sorted(set(clusters.values()))

    for cluster_id in all_cluster_ids:
        segment_ids = sorted(
            [sid for sid, cid in clusters.items() if cid == cluster_id]
        )
        placeholders = ",".join("?" * len(segment_ids))
        cursor.execute(
            f"""
            SELECT segment_id, score_id, start_note, end_note
            FROM Segment
            WHERE segment_id IN ({placeholders})
            ORDER BY segment_id
        """,
            segment_ids,
        )

        segment_details = cursor.fetchall()
        combined_notation = [
            f"{score_id}_{start}_{end}" for _, score_id, start, end in segment_details
        ]

        clusters_data.append(
            {
                "cluster_id": cluster_id,
                "segment_ids": ",".join(map(str, segment_ids)),
                "total_segments": len(segment_ids),
                "segments_notation": ",".join(combined_notation),
            }
        )

    return pd.DataFrame(clusters_data)


def save_results_to_excel(segments_df, clusters_df, output_dir, feature):
    """
    Save DataFrames to Excel files.

    Args:
        segments_df: DataFrame with segment details
        clusters_df: DataFrame with cluster details
        output_dir: Directory to save files
        feature: Feature type used for clustering
    """
    os.makedirs(output_dir, exist_ok=True)

    segments_df.to_excel(
        os.path.join(output_dir, f"segments_clustering_{feature}.xlsx"), index=False
    )
    clusters_df.to_excel(
        os.path.join(output_dir, f"clusters_details_{feature}.xlsx"), index=False
    )
