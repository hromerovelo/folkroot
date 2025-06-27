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
  This module contains utility functions for working with phylogenetic trees.
"""

import sqlite3
import random
import numpy as np
import pandas as pd
import sys
import os


def set_all_seeds(seed=42):
    """Set all random seeds for complete reproducibility."""
    random.seed(seed)
    np.random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)


def sanitize_filename(filename):
    """
    Sanitizes filename by removing accents and special characters.

    Args:
        filename (str): Original filename

    Returns:
        str: Sanitized filename with only alphanumeric characters, dots and underscores
    """
    import unicodedata

    # Remove accents from filename
    normalized = unicodedata.normalize("NFKD", filename)
    normalized = "".join(c for c in normalized if not unicodedata.combining(c))

    # Replace non-alphanumeric characters with underscores
    sanitized = "".join(
        c if c.isalnum() or c == "_" or c == "." else "_" for c in normalized
    )
    return sanitized


def connect_database(db_path):
    """Connects to SQLite database"""
    if not os.path.exists(db_path):
        print(f"Error: Database not found at {db_path}")
        sys.exit(1)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def get_scores_genre(conn):
    """Gets a dictionary that maps score_id to genre"""
    genre_mapping = {}
    cursor = conn.cursor()

    cursor.execute("SELECT score_id, genre FROM Score WHERE genre IS NOT NULL")
    for row in cursor.fetchall():
        score_id = row["score_id"]
        genre = row["genre"].lower()
        genre_mapping[score_id] = genre

    return genre_mapping


def get_total_genres(conn):
    """Gets the total number of unique genres from the database"""
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT LOWER(genre) FROM Score WHERE genre IS NOT NULL")
    genres = [row[0] for row in cursor.fetchall()]
    return len(genres), genres


def assign_genres_to_tree(tree, genre_mapping):
    """Assigns genre information to each node in the tree"""
    assigned = 0
    for node in tree.traverse():
        if node.is_leaf():
            # Leaf nodes have names like "123_filename.krn" where 123 is the score_id
            try:
                node_name = node.name.strip("'\"")
                score_id = int(node_name.split("_")[0])
                if score_id in genre_mapping:
                    node.add_feature("genre", genre_mapping[score_id])
                    assigned += 1
                else:
                    node.add_feature("genre", "unknown")
            except (ValueError, IndexError):
                # If score_id can't be extracted, assign "unknown"
                node.add_feature("genre", "unknown")

    return assigned


def normalize_matrix(matrix):
    """
    Normalize a matrix using min-max normalization.

    Args:
        matrix: numpy matrix to normalize

    Returns:
        normalized matrix with values between 0 and 1
    """
    if isinstance(matrix, pd.DataFrame):
        index_names = matrix.index
        column_names = matrix.columns
        values = matrix.values

        min_val = np.min(values)
        max_val = np.max(values)
        if max_val > min_val:
            normalized = (values - min_val) / (max_val - min_val)
        else:
            normalized = np.zeros_like(values)

        return pd.DataFrame(normalized, index=index_names, columns=column_names)
    else:
        min_val = np.min(matrix)
        max_val = np.max(matrix)
        if max_val > min_val:
            return (matrix - min_val) / (max_val - min_val)
        else:
            return np.zeros_like(matrix)
