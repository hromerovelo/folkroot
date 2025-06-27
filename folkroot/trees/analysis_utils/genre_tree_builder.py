"""
BSD 2-Clause License

Copyright (c) 2025, Hilda Romero-Velo
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

* Redistributions of source code must retain the above copyright notice, this
  list of conditions and the following disclaimer.

* Redistributions in binary form must reproduce the above copyright notice,
  this list of conditions and the following disclaimer in the documentation
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
  Utilities for building genre-level phylogenetic trees from distance matrices
  and calculating average distances between genres.
"""

import os
import sys
import numpy as np
import pandas as pd
import dendropy
from ete3 import Tree
from collections import Counter

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from trees_utils import set_all_seeds, sanitize_filename, connect_database
from .data_processing import get_scores_genre_by_ids_list, extract_score_id


def build_genre_tree(distance_matrix, output_nexus, random_seed=42):
    """
    Generates a phylogenetic tree using the neighbor-joining algorithm.

    Args:
        distance_matrix (numpy.ndarray): Distance matrix between genres
        output_nexus (str): Path to save the NEXUS format tree
        random_seed (int, optional): Random seed for reproducibility. Defaults to 42

    Returns:
        None: Writes tree file to disk
    """
    # Set random seed for reproducibility
    set_all_seeds(random_seed)

    # Create mapping between original and sanitized labels
    labels = distance_matrix.index.tolist()
    label_map = {label: sanitize_filename(label) for label in labels}
    sanitized_labels = [label_map[label] for label in labels]

    # Verify no collisions in sanitized names
    if len(set(sanitized_labels)) != len(labels):
        collision_groups = {}
        for orig, san in label_map.items():
            if san not in collision_groups:
                collision_groups[san] = []
            collision_groups[san].append(orig)

        collisions = {k: v for k, v in collision_groups.items() if len(v) > 1}
        if collisions:
            raise ValueError(f"Sanitization created duplicate names: {collisions}")

    # Reorder distance matrix and labels according to sorted sanitized labels
    sorted_indices = np.argsort(sanitized_labels)
    sorted_labels = [sanitized_labels[i] for i in sorted_indices]
    sorted_matrix = distance_matrix.values[sorted_indices][:, sorted_indices]

    # Create temporary CSV file with sorted matrix
    temp_path = output_nexus + ".temp.csv"
    with open(temp_path, "w") as f:
        f.write("," + ",".join(sorted_labels) + "\n")
        for i, label in enumerate(sorted_labels):
            row = [label] + [
                str(sorted_matrix[i, j]) for j in range(len(sorted_labels))
            ]
            f.write(",".join(row) + "\n")

    pdm = dendropy.PhylogeneticDistanceMatrix.from_csv(
        src=open(temp_path),
        delimiter=",",
    )

    # Generate neighbor-joining tree
    tree = pdm.nj_tree()

    # Configure tree properties and save to NEXUS file
    tree.is_rooted = False
    tree.write(
        path=output_nexus,
        schema="nexus",
        suppress_rooting=True,
        unquoted_underscores=True,
        store_tree_weights=True,
    )

    os.remove(temp_path)


def calculate_genre_distances(tree_file, db_path):
    """
    Calculate average distances between genres in the phylogenetic tree.
    Optimized for performance.
    """
    # Load tree using dendropy
    tree_dendro = dendropy.Tree.get(path=tree_file, schema="nexus")

    # Convert to newick format for ete3
    temp_newick = tree_file + ".temp.nw"
    tree_dendro.write(path=temp_newick, schema="newick")

    try:
        tree = Tree(temp_newick, format=1)
        leaf_nodes = tree.get_leaves()

        # Extract score_ids from leaf node names
        node_to_score_id = {}
        for node in leaf_nodes:
            clean_name = node.name.strip("'\"")
            score_id = extract_score_id(clean_name)
            if score_id:
                node_to_score_id[node] = score_id

        score_ids = list(node_to_score_id.values())

        # Connect to database and get genres
        db_conn = connect_database(db_path)
        score_genre_map = get_scores_genre_by_ids_list(db_conn, score_ids)

        # Map nodes to genres
        node_to_genre = {
            node: score_genre_map.get(score_id, "unknown")
            for node, score_id in node_to_score_id.items()
        }

        # Get unique genres
        genres = sorted(set(g for g in node_to_genre.values() if g != "unknown"))

        # Initialize distance matrix and count matrix
        genre_distances = {g1: {g2: 0.0 for g2 in genres} for g1 in genres}
        pair_counts = {g1: {g2: 0 for g2 in genres} for g1 in genres}

        # Calculate distances efficiently using triangle optimization
        n_leaf = len(leaf_nodes)
        for i in range(n_leaf):
            node1 = leaf_nodes[i]
            genre1 = node_to_genre.get(node1)
            if not genre1 or genre1 == "unknown":
                continue

            # Use range starting from i+1 to only calculate upper triangle
            for j in range(i + 1, n_leaf):
                node2 = leaf_nodes[j]
                genre2 = node_to_genre.get(node2)
                if not genre2 or genre2 == "unknown":
                    continue

                distance = max(0.0, tree.get_distance(node1, node2))

                # Add to distance matrix (both directions)
                genre_distances[genre1][genre2] += distance
                genre_distances[genre2][genre1] += distance

                # Increment count (both directions)
                pair_counts[genre1][genre2] += 1
                pair_counts[genre2][genre1] += 1

        # Calculate average distances
        for g1 in genres:
            for g2 in genres:
                if pair_counts[g1][g2] > 0:
                    genre_distances[g1][g2] /= pair_counts[g1][g2]

        # Convert to DataFrame
        df_distances = pd.DataFrame(genre_distances)

        # Get count of scores per genre
        genre_counts = Counter(
            node_to_genre.get(node)
            for node in leaf_nodes
            if node_to_genre.get(node) != "unknown"
        )

        db_conn.close()

        # Return data needed for metrics analysis
        metrics_data = {
            "valid_nodes": [n for n in leaf_nodes if node_to_genre.get(n) != "unknown"],
            "node_to_genre": node_to_genre,
            "tree": tree,
        }

        return df_distances, dict(genre_counts), metrics_data

    finally:
        # Clean up temporary file
        if os.path.exists(temp_newick):
            os.remove(temp_newick)
