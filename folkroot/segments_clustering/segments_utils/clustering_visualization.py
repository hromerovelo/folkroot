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

"""Functions for cluster visualization and PDF generation."""

import numpy as np
import os
import plotly.graph_objects as go
from PyPDF2 import PdfMerger
from sklearn.manifold import MDS
import subprocess
import tempfile
import verovio
import contextlib
import io
import sys
import concurrent.futures
import multiprocessing


def calculate_cluster_distances(cursor, clusters, score_column):
    """
    Calculate average distances between clusters using their centroids.

    Args:
        cursor: SQLite cursor
        clusters: Dictionary mapping segment_ids to cluster_ids
        score_column: Name of the score column to use

    Returns:
        dict: Dictionary with cluster distances and centroids
    """
    cluster_info = {}
    cluster_ids = set(clusters.values())

    # Calculate centroid distances between clusters
    for c1 in cluster_ids:
        cluster1_segments = [sid for sid, cid in clusters.items() if cid == c1]
        for c2 in cluster_ids:
            if c2 > c1:  # Avoid duplicate calculations
                cluster2_segments = [sid for sid, cid in clusters.items() if cid == c2]

                # Get average distance between segments in clusters
                placeholders1 = ",".join(["?" for _ in cluster1_segments])
                placeholders2 = ",".join(["?" for _ in cluster2_segments])

                cursor.execute(
                    f"""
                    SELECT AVG({score_column})
                    FROM segmentalignment
                    WHERE segment_id_1 IN ({placeholders1})
                    AND segment_id_2 IN ({placeholders2})
                """,
                    cluster1_segments + cluster2_segments,
                )

                avg_distance = cursor.fetchone()[0] or 0

                if c1 not in cluster_info:
                    cluster_info[c1] = {"distances": {}}
                if c2 not in cluster_info:
                    cluster_info[c2] = {"distances": {}}

                cluster_info[c1]["distances"][c2] = avg_distance
                cluster_info[c2]["distances"][c1] = avg_distance

    return cluster_info


def create_cluster_visualization(clusters_df, cluster_info, output_dir, feature):
    """
    Create interactive visualization of clusters using Plotly.

    Args:
        clusters_df: DataFrame with cluster information
        cluster_info: Dictionary with cluster distances
        output_dir: Directory to save the HTML file
        feature: Feature type used for clustering
    """
    # Prepare distance matrix for MDS
    cluster_ids = sorted(list(cluster_info.keys()))
    n_clusters = len(cluster_ids)
    distances = np.zeros((n_clusters, n_clusters))

    for i, c1 in enumerate(cluster_ids):
        for j, c2 in enumerate(cluster_ids):
            if i != j:
                distances[i, j] = cluster_info[c1]["distances"].get(c2, 0)

    # Use MDS to convert distances to 2D coordinates
    mds = MDS(n_components=2, dissimilarity="precomputed", random_state=42)
    coords = mds.fit_transform(distances)

    # Create visualization
    sizes = clusters_df["total_segments"].values * 10  # Scale sizes for visibility

    fig = go.Figure()

    # Add scatter plot
    fig.add_trace(
        go.Scatter(
            x=coords[:, 0],
            y=coords[:, 1],
            mode="markers",
            marker=dict(
                size=sizes,
                sizemode="area",
                sizeref=2.0 * max(sizes) / (40.0**2),
                sizemin=4,
            ),
            text=[
                f"Cluster {cid}<br>"
                f"Segments: {row['total_segments']}<br>"
                f"IDs: {row['segment_ids']}"
                for cid, row in clusters_df.iterrows()
            ],
            hoverinfo="text",
        )
    )

    fig.update_layout(
        title=f"Cluster Visualization - {feature}",
        xaxis_title="Dimension 1",
        yaxis_title="Dimension 2",
        showlegend=False,
    )

    # Save to HTML
    fig.write_html(os.path.join(output_dir, f"cluster_visualization_{feature}.html"))


@contextlib.contextmanager
def suppress_warnings():
    """Temporarily suppress warnings and stdout"""
    stdout = sys.stdout
    stderr = sys.stderr
    null = open(os.devnull, "w")
    sys.stdout = null
    sys.stderr = null
    try:
        yield
    finally:
        sys.stdout = stdout
        sys.stderr = stderr
        null.close()


def process_cluster(args):
    """
    Process all segments in a cluster and create its PDF

    Args:
        args: Tuple with cluster_id, segment_ids, segment_paths, tk_options
    """
    cluster_id, segment_ids, segment_paths, tk_options = args

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_pdfs = []

            # Process each segment in the cluster
            tk = verovio.toolkit()
            tk.setOptions(tk_options)

            for segment_id in segment_ids:
                segment_path = segment_paths.get(segment_id)
                if not (segment_path and os.path.exists(segment_path)):
                    continue

                try:
                    # Read kern file
                    with open(segment_path, "r") as f:
                        kern_data = f.read()

                    # Generate SVG and PDF
                    temp_svg = os.path.join(temp_dir, f"{segment_id}.svg")
                    temp_pdf = os.path.join(temp_dir, f"{segment_id}.pdf")

                    with suppress_warnings():
                        tk.loadData(
                            f"!!!header: File: {os.path.basename(segment_path)}\n{kern_data}"
                        )
                        tk.renderToSVGFile(temp_svg)

                    subprocess.run(
                        [
                            "inkscape",
                            "--export-filename=" + temp_pdf,
                            "--export-type=pdf",
                            "--export-dpi=300",
                            "--export-background=white",
                            temp_svg,
                        ],
                        check=True,
                        capture_output=True,
                    )

                    temp_pdfs.append(temp_pdf)

                except Exception as e:
                    return (
                        cluster_id,
                        None,
                        f"Error processing segment {segment_id}: {e}",
                    )

            # Merge PDFs for this cluster if any were generated
            if temp_pdfs:
                merger = PdfMerger()
                for pdf in temp_pdfs:
                    merger.append(pdf)
                pdf_data = io.BytesIO()
                merger.write(pdf_data)
                merger.close()
                return cluster_id, pdf_data.getvalue(), None

            return cluster_id, None, "No PDFs generated for cluster"

    except Exception as e:
        return cluster_id, None, f"Error processing cluster: {e}"


def create_cluster_pdfs(clusters_df, output_dir, feature, cursor, script_dir):
    """
    Create PDF files for each cluster using parallel processing

    Args:
        clusters_df: DataFrame with cluster information
        output_dir: Directory to save the PDF files
        feature: Feature type used for clustering
        cursor: SQLite cursor
        script_dir: Directory of the script for segment paths
    """
    # Initialize Verovio toolkit options
    tk_options = {
        "scale": 40,
        "pageHeight": 3000,
        "pageWidth": 2300,
        "adjustPageHeight": True,
        "spacingStaff": 8,
        "spacingSystem": 12,
        "breaks": "auto",
    }

    pdf_dir = os.path.join(output_dir, f"cluster_pdfs_{feature}")
    os.makedirs(pdf_dir, exist_ok=True)

    # Get all segment paths upfront
    cursor.execute(
        """
        SELECT s.segment_id, sc.filename, s.start_note, s.end_note
        FROM Segment s
        JOIN Score sc ON s.score_id = sc.score_id
    """
    )
    segment_paths = {
        str(sid): os.path.join(
            script_dir,
            f"../data/segments/{os.path.splitext(fname)[0]}_{start}_{end}_{sid}.krn",
        )
        for sid, fname, start, end in cursor.fetchall()
    }

    total_clusters = len(clusters_df)
    processed = 0
    errors = []

    print(f"\nProcessing {total_clusters} clusters...")

    # Process clusters in parallel
    max_workers = max(1, multiprocessing.cpu_count() - 1)
    with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
        # Prepare tasks for all clusters
        futures = []
        for _, row in clusters_df.iterrows():
            cluster_id = row["cluster_id"]
            segment_ids = row["segment_ids"].split(",")
            futures.append(
                executor.submit(
                    process_cluster,
                    (cluster_id, segment_ids, segment_paths, tk_options),
                )
            )

        # Process results as they complete
        for future in concurrent.futures.as_completed(futures):
            processed += 1
            print(
                f"\rProcessed {processed}/{total_clusters} clusters", end="", flush=True
            )

            cluster_id, pdf_data, error = future.result()
            if error:
                errors.append((cluster_id, error))
                print(f"\nError in cluster {cluster_id}: {error}")
            elif pdf_data:
                # Write PDF to file
                pdf_path = os.path.join(pdf_dir, f"cluster_{cluster_id}.pdf")
                with open(pdf_path, "wb") as f:
                    f.write(pdf_data)

    print(f"\nProcessed {total_clusters}/{total_clusters} clusters")
    print("\nPDF generation completed!")

    if errors:
        print(f"\nWarning: {len(errors)} clusters had errors")
        with open(os.path.join(output_dir, "processing_errors.txt"), "w") as f:
            f.write("\n".join(f"Cluster {cid}: {err}" for cid, err in errors))

    print(f"\nCluster PDFs saved in {pdf_dir}")
