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
  This script generates a phylogenetic tree from a distance matrix of scores.
  The distance matrix is calculated using alignment scores from a SQLite database.
  The script uses the neighbor-joining algorithm to generate the tree and saves it in NEXUS format.
"""

import os
import sqlite3
import dendropy
import numpy as np
import argparse
import pandas as pd
from trees_utils import set_all_seeds, sanitize_filename, normalize_matrix


def save_distance_matrix_to_excel(distance_matrix, filenames, output_path):
    """
    Save the distance matrix to an Excel file.

    Args:
        distance_matrix (numpy.ndarray): The distance matrix
        filenames (list): List of filenames/taxa used as row and column labels
        output_path (str): Path to save the Excel file

    Returns:
        None: Writes Excel file to disk
    """
    df = pd.DataFrame(distance_matrix, index=filenames, columns=filenames)
    df.to_excel(output_path, index=True)
    print(f"Distance matrix saved to {output_path}")


def get_alignment_matrix(
    cursor, level_name, feature, score_mapping, genre_filter, params
):
    """
    Fetch and fill alignment matrix for a specific level.

    Args:
        cursor: SQLite database cursor
        level_name: Level of alignment (note, structure, shared_segments)
        feature: Feature type (diatonic, chromatic, rhythmic, etc.)
        score_mapping: Dictionary mapping score_id to (index, filename)
        genre_filter: SQL genre filter condition
        params: Parameters for the SQL query

    Returns:
        numpy matrix with alignment scores
    """
    n = len(score_mapping)
    matrix = np.zeros((n, n))
    query_params = [level_name] + params.copy()

    cursor.execute(
        f"""
        SELECT s1.score_id, s2.score_id, sa.{feature}_score
        FROM Score s1
        JOIN ScoreAlignment sa ON s1.score_id = sa.score_id_1
        JOIN Score s2 ON s2.score_id = sa.score_id_2
        WHERE sa.level = ? {genre_filter}
        """,
        query_params,
    )

    for score_id1, score_id2, score_value in cursor.fetchall():
        if (
            score_value is not None
            and score_id1 in score_mapping
            and score_id2 in score_mapping
        ):
            i = score_mapping[score_id1][0]
            j = score_mapping[score_id2][0]
            matrix[i, j] = score_value
            matrix[j, i] = score_value  # Matrix should be symmetric

    return matrix


def get_distance_matrix(
    db_path, feature, level="note", genres=None, structure_weight=None
):
    """
    Retrieves distance scores from SQLite database and builds a distance matrix.
    If structure_weight is provided, combines structure and shared_segments levels.

    Args:
        db_path (str): Path to SQLite database
        feature (str): Feature to use for distance calculation
        level (str, optional): Level of alignment. Defaults to "note"
        genres (list, optional): List of genres to filter by. If None, includes all genres
        structure_weight (float, optional): Weight for structure level (0-1).
                                           If provided, combines structure and shared_segments levels.

    Returns:
        tuple: (numpy.ndarray, list) - Distance matrix and list of filenames
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get score mapping with optional genre filtering
    base_query = """
        SELECT DISTINCT s.score_id, s.filename 
        FROM Score s
        {}
        ORDER BY s.score_id
    """

    genre_clause = ""
    if genres:
        genre_clause = "WHERE genre IN ({})".format(",".join(["?"] * len(genres)))
        cursor.execute(base_query.format(genre_clause), genres)
    else:
        cursor.execute(base_query.format(""))

    # Modify filenames to include score_id
    score_mapping = {
        row[0]: (i, f"{row[0]}_{row[1]}") for i, row in enumerate(cursor.fetchall())
    }

    # Create empty matrix and filename list
    n = len(score_mapping)
    if n == 0:
        conn.close()
        raise ValueError("No scores found with the specified genres")

    # Create filename list with score_id prefix
    filenames = [
        score_mapping[score_id][1] for score_id in sorted(score_mapping.keys())
    ]

    # Prepare genre filter for alignment queries
    genre_filter = ""
    params = []
    if genres:
        genre_filter = "AND s1.genre IN ({}) AND s2.genre IN ({})".format(
            ",".join(["?"] * len(genres)), ",".join(["?"] * len(genres))
        )
        params.extend(genres * 2)

    # Handle combined level case (structure + shared_segments)
    if structure_weight is not None:
        # Validate structure_weight
        if not 0 <= structure_weight <= 1:
            conn.close()
            raise ValueError("structure_weight must be between 0 and 1")

        shared_segments_weight = 1 - structure_weight

        # Get matrices for both levels
        structure_matrix = get_alignment_matrix(
            cursor, "structure", feature, score_mapping, genre_filter, params
        )
        shared_segments_matrix = get_alignment_matrix(
            cursor, "shared_segments", feature, score_mapping, genre_filter, params
        )

        # Normalize both matrices
        norm_structure_matrix = normalize_matrix(structure_matrix)
        norm_shared_matrix = normalize_matrix(shared_segments_matrix)

        # Combine normalized matrices with weights
        combined_matrix = np.zeros_like(structure_matrix)
        both_valid = (structure_matrix > 0) & (shared_segments_matrix > 0)

        combined_matrix[both_valid] = (
            structure_weight * norm_structure_matrix[both_valid]
            + shared_segments_weight * norm_shared_matrix[both_valid]
        )

        # Scale back to a reasonable range for compatibility
        distance_matrix = combined_matrix * 1000
    else:
        # Standard single-level approach
        distance_matrix = get_alignment_matrix(
            cursor, level, feature, score_mapping, genre_filter, params
        )

    conn.close()
    return distance_matrix, filenames


def build_tree(distance_matrix, labels, output_nexus, random_seed=42):
    """
    Generates a phylogenetic tree using the neighbor-joining algorithm.

    Args:
        distance_matrix (numpy.ndarray): Distance matrix between sequences
        labels (list): List of filenames/taxa
        output_nexus (str): Path to save the NEXUS format tree
        random_seed (int, optional): Random seed for reproducibility. Defaults to 42

    Returns:
        None: Writes tree file to disk
    """

    # Create mapping between original and sanitized labels
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
    sorted_matrix = distance_matrix[sorted_indices][:, sorted_indices]

    # Create temporary CSV file with sorted matrix
    temp_path = output_nexus + ".temp.csv"
    with open(temp_path, "w") as f:
        f.write("," + ",".join(sorted_labels) + "\n")
        for i, label in enumerate(sorted_labels):
            row = [label] + [
                str(sorted_matrix[i, j]) for j in range(len(sorted_labels))
            ]
            f.write(",".join(row) + "\n")

    # Read distance matrix from CSV file
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


if __name__ == "__main__":
    """
    Main function to parse arguments, set up paths and generate phylogenetic tree.
    Sets up argument parser, creates output directories, generates tree and iTOL annotations.

    Args:
        None: Uses command line arguments

    Returns:
        None: Writes tree and annotation files to disk
    """
    parser = argparse.ArgumentParser(
        description="Generates a phylogenetic tree from a distance matrix"
    )
    parser.add_argument(
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
        help="Type of feature to use for distance calculation",
    )
    parser.add_argument(
        "--level",
        type=str,
        choices=["note", "structure", "shared_segments", "combined"],
        help="Level of alignment to use for distance calculation. Use 'combined' for a weighted combination of structure and shared_segments.",
    )

    parser.add_argument(
        "--structure-weight",
        type=float,
        default=0.5,
        help="Weight for structure level when using --level combined (0.0-1.0). Default: 0.5. The shared_segments weight will be (1 - structure_weight).",
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility (default: 42)",
    )

    parser.add_argument(
        "--genres",
        nargs="+",
        help="Only include scores from these genres (space-separated list). If not specified, includes all genres",
    )

    # Add this to the argument parser section
    parser.add_argument(
        "--save-matrix",
        action="store_true",
        help="Save the distance matrix to an Excel file",
    )

    args = parser.parse_args()

    # Set default level if not provided
    if not args.level:
        args.level = "note"

    # Validate structure weight for combined level
    if args.level == "combined" and (
        args.structure_weight < 0 or args.structure_weight > 1
    ):
        parser.error("--structure-weight must be between 0.0 and 1.0")

    # Set all random seeds at the start
    set_all_seeds(args.seed)

    script_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.abspath(os.path.join(script_dir, "../database/folkroot.db"))

    if args.level == "combined":
        output_dir = os.path.join(
            script_dir,
            "generated_trees",
            f"combined_level_s{int(args.structure_weight*100)}_ss{int((1-args.structure_weight)*100)}",
        )
    else:
        output_dir = os.path.join(script_dir, "generated_trees", args.level + "_level")

    os.makedirs(output_dir, exist_ok=True)

    # Modify directory and file naming to include genre information
    genre_suffix = "_".join(args.genres) if args.genres else "all_genres"

    if args.level == "combined":
        level_name = f"combined_s{int(args.structure_weight*100)}_ss{int((1-args.structure_weight)*100)}"
        run_dir = f"{level_name}_{args.feature}_{genre_suffix}"
    else:
        run_dir = f"{args.level}_level_{args.feature}_{genre_suffix}"

    output_dir = os.path.join(output_dir, run_dir)
    os.makedirs(output_dir, exist_ok=True)

    # Output filename for the phylogenetic tree
    output_nexus = f"{run_dir}_phylogenetic_tree.nexus"
    output_path = os.path.join(output_dir, output_nexus)

    # Generate distance matrix and build tree
    if args.level == "combined":
        distance_matrix, filenames = get_distance_matrix(
            db_path, args.feature, None, args.genres, args.structure_weight
        )
    else:
        distance_matrix, filenames = get_distance_matrix(
            db_path, args.feature, args.level, args.genres
        )

    if args.save_matrix:
        excel_output = os.path.join(output_dir, f"{run_dir}_distance_matrix.xlsx")
        save_distance_matrix_to_excel(distance_matrix, filenames, excel_output)

    build_tree(distance_matrix, filenames, output_path, random_seed=args.seed)

    print(f"Phylogenetic tree generated in {output_path}")
