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
  Data processing functions for genre distance analysis.
"""
import os
import re
import seaborn as sns
import matplotlib.pyplot as plt


def get_scores_genre_by_ids_list(db_conn, score_ids):
    """Get genre for each score ID from the database."""
    cursor = db_conn.cursor()

    query = """
    SELECT score_id, genre
    FROM Score
    WHERE score_id IN ({})
    """.format(
        ",".join("?" * len(score_ids))
    )

    cursor.execute(query, score_ids)
    score_genre_map = {row["score_id"]: row["genre"] for row in cursor.fetchall()}
    return score_genre_map


def extract_score_id(taxon_label):
    """Extract score_id from taxon label in format {score_id}_{filename}."""
    try:
        clean_taxon_label = taxon_label.strip("'").replace(" ", "_")
        score_id = int(clean_taxon_label.split("_")[0])
        return score_id
    except (ValueError, IndexError):
        print(f"Warning: Could not extract score_id from label: {taxon_label}")
        return None


def find_tree_files(directory):
    """
    Find phylogenetic tree files in a directory.

    Args:
        directory (str): Directory to search in

    Returns:
        list: List of NEXUS tree files paths
    """
    tree_files = []

    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(".nexus"):
                if "_phylogenetic_tree.nexus" in file and "genre_tree" not in file:
                    full_path = os.path.join(root, file)
                    tree_files.append(full_path)
                    print(f"Found tree file: {full_path}")

    return sorted(tree_files)


def generate_distance_heatmap(
    matrix, output_path, title=None, cmap="cividis_r", annot=True
):
    """
    Generate a heatmap for a distance matrix and save it as an image.

    Args:
        matrix (pd.DataFrame): Distance matrix between genres
        output_path (str): Path to save the image
        title (str, optional): Chart title
        cmap (str, optional): Color map for the heatmap
        annot (bool, optional): Whether to show numeric values in cells
    """
    plt.figure(figsize=(max(12, len(matrix) // 2), max(10, len(matrix) // 2)))

    # Create a customized heatmap if there are many genres
    if len(matrix) > 30:
        annot = False  # Disable annotations if there are too many genres

    # Generate heatmap
    heatmap = sns.heatmap(
        matrix,
        annot=annot,
        fmt=".2f" if annot else "",
        cmap=cmap,
        linewidths=0.5,
        square=True,
        cbar=False,
        # cbar_kws={"shrink": 0.8, "label": "Normalized Distance"},
        annot_kws={"size": 10, "weight": "bold"},
    )

    # Configure title and layout
    if title:
        plt.title(title, fontsize=16, pad=20, weight="bold")

    plt.tight_layout()

    # Rotate labels if there are many genres
    if len(matrix) > 15:
        plt.xticks(rotation=90, fontsize=13, weight="bold")
        plt.yticks(rotation=0, fontsize=13, weight="bold")

    # Save chart
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()

    print(f"Heatmap saved to {output_path}")


def extract_level_feature(tree_name):
    """Extract level and feature from tree name using pattern matching."""
    # Precompile regex patterns for better performance
    if not hasattr(extract_level_feature, "patterns"):
        extract_level_feature.patterns = {
            "combined_simple": re.compile(r"combined_(s\d+_ss\d+)_([^_]+)_all_genres"),
            "combined_level": re.compile(
                r"combined_level_(s\d+_ss\d+)_([^_]+)_all_genres"
            ),
            "combined_diatonic": re.compile(
                r"combined_(s\d+_ss\d+)_diatonic_rhythmic_all_genres"
            ),
            "combined_chromatic": re.compile(
                r"combined_(s\d+_ss\d+)_chromatic_rhythmic_all_genres"
            ),
            "level_feature": re.compile(
                r"(note|structure|shared_segments)_level_([^_]+)_all_genres"
            ),
            "level_diatonic": re.compile(
                r"(note|structure|shared_segments)_level_diatonic_rhythmic_all_genres"
            ),
            "level_chromatic": re.compile(
                r"(note|structure|shared_segments)_level_chromatic_rhythmic_all_genres"
            ),
        }

    # Extract using compiled patterns
    if "combined_s" in tree_name:
        # Try combined patterns
        match = extract_level_feature.patterns["combined_simple"].search(tree_name)
        if match:
            combined_weights, feature = match.groups()
            return f"combined_{combined_weights}", feature

        match = extract_level_feature.patterns["combined_level"].search(tree_name)
        if match:
            combined_weights, feature = match.groups()
            return f"combined_{combined_weights}", feature

        # Special feature patterns
        if "_diatonic_rhythmic_" in tree_name:
            match = extract_level_feature.patterns["combined_diatonic"].search(
                tree_name
            )
            if match:
                combined_weights = match.group(1)
                return f"combined_{combined_weights}", "diatonic_rhythmic"
            return "combined", "diatonic_rhythmic"

        if "_chromatic_rhythmic_" in tree_name:
            match = extract_level_feature.patterns["combined_chromatic"].search(
                tree_name
            )
            if match:
                combined_weights = match.group(1)
                return f"combined_{combined_weights}", "chromatic_rhythmic"
            return "combined", "chromatic_rhythmic"

        return "combined", "unknown"
    else:
        # Regular level patterns
        if "_diatonic_rhythmic_" in tree_name:
            match = extract_level_feature.patterns["level_diatonic"].search(tree_name)
            if match:
                return match.group(1), "diatonic_rhythmic"
            return "unknown", "diatonic_rhythmic"

        if "_chromatic_rhythmic_" in tree_name:
            match = extract_level_feature.patterns["level_chromatic"].search(tree_name)
            if match:
                return match.group(1), "chromatic_rhythmic"
            return "unknown", "chromatic_rhythmic"

        # Regular pattern
        match = extract_level_feature.patterns["level_feature"].search(tree_name)
        if match:
            return match.groups()

        # Last attempt with direct checks
        level = "unknown"
        if "note_level" in tree_name:
            level = "note"
        elif "structure_level" in tree_name:
            level = "structure"
        elif "shared_segments_level" in tree_name:
            level = "shared_segments"

        feature = "unknown"
        if "_diatonic_" in tree_name and not "_diatonic_rhythmic_" in tree_name:
            feature = "diatonic"
        elif "_chromatic_" in tree_name and not "_chromatic_rhythmic_" in tree_name:
            feature = "chromatic"
        elif "_rhythmic_" in tree_name:
            if "_diatonic_rhythmic_" in tree_name:
                feature = "diatonic_rhythmic"
            elif "_chromatic_rhythmic_" in tree_name:
                feature = "chromatic_rhythmic"
            else:
                feature = "rhythmic"

        return level, feature
