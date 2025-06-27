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
import os
import sqlite3
from ete3 import TreeStyle, TextFace

COLOR_PALETTE = [
    "#1f77b4",  # blue
    "#ff7f0e",  # orange
    "#2ca02c",  # green
    "#d62728",  # red
    "#9467bd",  # purple
    "#8c564b",  # brown
    "#e377c2",  # pink
    "#bcbd22",  # olive
    "#17becf",  # teal
    "#7f7f7f",  # gray
    "#aec7e8",  # light blue
    "#ffbb78",  # light orange
    "#98df8a",  # light green
    "#ff9896",  # light red
    "#c5b0d5",  # light purple
    "#c49c94",  # light brown
    "#f7b6d2",  # light pink
    "#dbdb8d",  # light olive
    "#9edae5",  # light teal
    "#c7c7c7",  # light gray
    "#ff6347",  # tomato
]

DATASET_COLORS = {
    "galician": "#45c6ac",  # turquoise
    "irish": "#55a2d6",  # blue
    "unknown": "#a0a0a0",  # grey
}


def is_genre_tree(tree_file):
    """Check if the tree is a genre tree by its filename."""
    base_name = os.path.basename(tree_file)
    return base_name.startswith("genre_tree_")


def lighten_hex_color(hex_color, fraction=0.4):
    """Return a lighter version of the given hex color."""
    hex_color = hex_color.lstrip("#")
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)

    r = int(r + (255 - r) * fraction)
    g = int(g + (255 - g) * fraction)
    b = int(b + (255 - b) * fraction)

    return f"#{r:02x}{g:02x}{b:02x}"


def extract_short_name(taxon_label):
    """Extract the short name from a taxon label."""
    clean_name = taxon_label.strip("'\"")
    parts = clean_name.split("_")
    if len(parts) > 1:
        filename = "_".join(parts[1:])
        short_name = os.path.basename(filename)
        if short_name.endswith(".krn"):
            short_name = short_name[:-4]
    else:
        short_name = clean_name
    return short_name


def get_colored_genres(conn):
    """Get all genres from the database with assigned colors."""
    if not conn:
        return {}

    cursor = conn.cursor()
    genre_colors = {}

    try:
        cursor.execute(
            """
            SELECT genre, COUNT(*) as count 
            FROM Score 
            WHERE genre IS NOT NULL AND genre != ''
            GROUP BY genre
            ORDER BY count DESC
        """
        )
        rows = cursor.fetchall()

        # Assign colors to genres
        for i, row in enumerate(rows):
            genre = row["genre"].lower()
            color_idx = i % len(COLOR_PALETTE)
            genre_colors[genre] = COLOR_PALETTE[color_idx]

        return genre_colors
    except sqlite3.Error as e:
        print(f"Error fetching genres: {e}")
        return {}


def get_genre_dataset_mapping(conn):
    """Get mapping of genres to dataset."""
    if not conn:
        return {}

    cursor = conn.cursor()
    genre_dataset_map = {}

    try:
        cursor.execute(
            """
            SELECT DISTINCT genre, dataset
            FROM Score
            WHERE genre IS NOT NULL AND genre != '' AND dataset IS NOT NULL
            GROUP BY genre
        """
        )
        rows = cursor.fetchall()

        for row in rows:
            genre = row["genre"].lower()
            dataset = row["dataset"].lower()
            genre_dataset_map[genre] = dataset

        return genre_dataset_map
    except sqlite3.Error as e:
        print(f"Error fetching genre-dataset mapping: {e}")
        return {}


def get_score_metadata(conn, taxon_label):
    """Get genre and dataset for a score from its label."""
    if not conn:
        return "unknown", "unknown"

    cursor = conn.cursor()

    try:
        # Extract score_id from the label format "<score_id>_<filename>"
        clean_taxon_label = taxon_label.strip().strip("'\"").replace(" ", "_")
        score_id = int(clean_taxon_label.split("_")[0])

        # Query using score_id
        cursor.execute(
            """
            SELECT genre, dataset 
            FROM Score 
            WHERE score_id = ?
            """,
            (score_id,),
        )
        row = cursor.fetchone()

        if row and row["genre"] and row["dataset"]:
            return row["genre"].lower(), row["dataset"].lower()

        print(f"No metadata found for score_id: {score_id} (label: {taxon_label})")

    except (ValueError, IndexError) as e:
        print(f"Error parsing score_id from label {taxon_label}: {e}")
    except sqlite3.Error as e:
        print(f"Database query error for {taxon_label}: {e}")

    return "unknown", "unknown"


def create_tree_style(title):
    """
    Create a custom tree style with the given title and configuration.
    """
    ts = TreeStyle()
    ts.show_leaf_name = False
    ts.branch_vertical_margin = 15
    ts.scale = 120

    title_face = TextFace(title, fsize=16, fgcolor="black", bold=True)
    title_face.margin_bottom = 10
    ts.title.add_face(title_face, column=0)

    ts.rotation = 0
    ts.show_scale = False
    ts.show_branch_length = False
    ts.margin_right = 250
    ts.margin_top = 50
    ts.margin_bottom = 50
    ts.min_leaf_separation = 15
    ts.show_branch_support = False

    ts.legend_position = 1

    return ts
