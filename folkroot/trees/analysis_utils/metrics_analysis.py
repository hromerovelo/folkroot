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
  Functions for calculating Genre Separation Ratio.
"""

import os
import sys
import dendropy
import numpy as np
from ete3 import Tree

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from trees_utils import connect_database
from .data_processing import get_scores_genre_by_ids_list, extract_score_id


def calculate_genre_separation_ratio(tree_file, db_path):
    """
    Calculate the Genre Separation Ratio (GSR) for each genre in the phylogenetic tree.

    Args:
        tree_file (str): Path to the tree file in NEXUS format
        db_path (str): Path to the SQLite database

    Returns:
        dict: Dictionary with GSR values for each genre
    """
    # Load tree using dendropy which handles NEXUS format properly
    tree_dendro = dendropy.Tree.get(path=tree_file, schema="nexus")

    # Convert to newick format for ete3
    temp_newick = tree_file + ".temp.nw"
    tree_dendro.write(path=temp_newick, schema="newick")

    try:
        # Now load with ete3 which has better distance calculation
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

        # Initialize distance matrices and count matrices
        within_genre_distances = {g: [] for g in genres}
        between_genre_distances = {g: [] for g in genres}

        # Calculate distances efficiently using triangle optimization
        n_leaf = len(leaf_nodes)
        for i in range(n_leaf):
            node1 = leaf_nodes[i]
            genre1 = node_to_genre.get(node1)
            if not genre1 or genre1 == "unknown":
                continue

            for j in range(i + 1, n_leaf):
                node2 = leaf_nodes[j]
                genre2 = node_to_genre.get(node2)
                if not genre2 or genre2 == "unknown":
                    continue

                # Get distance
                distance = max(0.0, tree.get_distance(node1, node2))

                if genre1 == genre2:
                    within_genre_distances[genre1].append(distance)
                else:
                    between_genre_distances[genre1].append(distance)
                    between_genre_distances[genre2].append(distance)

        # Calculate average distances
        gsr_values = {}
        for genre in genres:
            within_avg = (
                np.mean(within_genre_distances[genre])
                if within_genre_distances[genre]
                else 0
            )
            between_avg = (
                np.mean(between_genre_distances[genre])
                if between_genre_distances[genre]
                else 0
            )
            if within_avg > 0:
                gsr_values[genre] = between_avg / within_avg
            else:
                gsr_values[genre] = float("inf")  # Handle case where within_avg is 0

        db_conn.close()
        return gsr_values

    finally:
        # Clean up temporary file
        if os.path.exists(temp_newick):
            os.remove(temp_newick)
