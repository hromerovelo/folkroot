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
  Created by Hilda Romero-Velo on June 2025.
"""

"""
  Script to evaluate the sensitivity of GSR (Genre Separation Ratio)
  by introducing noise in genre assignments.
"""

import os
import sys
import random
import numpy as np
import matplotlib.pyplot as plt
import dendropy
from ete3 import Tree

# Import necessary functions
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from trees_utils import connect_database
from analysis_utils.metrics_analysis import calculate_genre_separation_ratio


def get_all_scores_with_genres(db_conn):
    """Get all scores with their genres from the database"""
    cursor = db_conn.cursor()
    cursor.execute("SELECT score_id, genre FROM Score")
    return {row[0]: row[1] for row in cursor.fetchall()}


def build_perfect_tree(scores_genres, output_dir):
    """
    Build a 'perfect' tree where scores of the same genre
    are grouped together with minimal distances.
    """
    # Group scores by genre
    genres_to_scores = {}
    for score_id, genre in scores_genres.items():
        if genre not in genres_to_scores:
            genres_to_scores[genre] = []
        genres_to_scores[genre].append(score_id)

    # Create a tree using ete3
    tree = Tree()

    # For each genre, create a subtree
    for genre, score_ids in genres_to_scores.items():
        # Create a node for the genre
        genre_node = tree.add_child(name=f"Genre_{genre}")
        genre_node.dist = 5.0  # Large distance between genres

        # Add each score as a leaf with format {score_id}_{genre}_synthetic.krn
        for score_id in score_ids:
            # Use format compatible with extract_score_id
            leaf = genre_node.add_child(name=f"{score_id}_{genre}_synthetic.krn")
            leaf.dist = 0.1  # Small distance within the same genre

    # Save as Newick file
    os.makedirs(output_dir, exist_ok=True)
    newick_path = os.path.join(output_dir, "perfect_tree.nw")
    tree.write(outfile=newick_path, format=1)

    # Convert to NEXUS using dendropy
    tree_dendro = dendropy.Tree.get(path=newick_path, schema="newick")
    nexus_path = os.path.join(output_dir, "perfect_tree.nex")
    tree_dendro.write(path=nexus_path, schema="nexus")

    return nexus_path


def introduce_noise(original_genres, noise_percentage):
    """
    Introduce noise by randomly changing a percentage of genre assignments.
    """
    noisy_genres = original_genres.copy()
    all_genres = list(set(original_genres.values()))

    # Number of scores to change
    n_changes = int(len(noisy_genres) * noise_percentage / 100)

    # Randomly select scores
    scores_to_change = random.sample(list(noisy_genres.keys()), n_changes)

    # Change their genres
    for score_id in scores_to_change:
        current_genre = noisy_genres[score_id]
        available_genres = [g for g in all_genres if g != current_genre]
        if available_genres:
            noisy_genres[score_id] = random.choice(available_genres)

    return noisy_genres


def test_gsr_sensitivity(db_path):
    """
    Test the sensitivity of GSR by introducing different levels of noise.
    """
    db_conn = connect_database(db_path)

    original_genres = get_all_scores_with_genres(db_conn)

    # Noise levels to test
    noise_levels = [0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50]
    gsr_results = {}
    avg_gsr_results = []

    output_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "gsr_sensitivity_results"
    )
    os.makedirs(output_dir, exist_ok=True)

    for noise in noise_levels:
        print(f"Testing with {noise}% noise...")

        noisy_genres = introduce_noise(original_genres, noise)

        noise_dir = os.path.join(output_dir, f"noise_{noise}")
        os.makedirs(noise_dir, exist_ok=True)

        # Build tree based on noisy genres
        tree_path = build_perfect_tree(noisy_genres, noise_dir)

        # Save genre map for reference
        with open(os.path.join(noise_dir, "genres_map.txt"), "w") as f:
            for score_id, genre in sorted(noisy_genres.items()):
                f.write(f"{score_id}_{genre}_synthetic.krn: {genre}\n")

        # Calculate GSR
        gsr_values = calculate_genre_separation_ratio(tree_path, db_path)

        with open(os.path.join(noise_dir, "gsr_results.txt"), "w") as f:
            for genre, gsr in sorted(gsr_values.items()):
                f.write(f"{genre}: {gsr}\n")

        gsr_results[noise] = gsr_values
        avg_gsr = np.mean(list(gsr_values.values()))
        avg_gsr_results.append(avg_gsr)

        print(f"Average GSR with {noise}% noise: {avg_gsr:.4f}")

    # Plot results
    plt.figure(figsize=(10, 6))
    plt.plot(noise_levels, avg_gsr_results, marker="o")
    plt.xlabel("Noise Level (%)")
    plt.ylabel("Average GSR")
    plt.title("GSR Sensitivity to Noise in Genre Assignment")
    plt.grid(True)
    plt.savefig(os.path.join(output_dir, "gsr_sensitivity.png"))

    # Plot individual GSR by genre
    plt.figure(figsize=(12, 8))
    genres = list(gsr_results[0].keys())

    for genre in genres:
        genre_gsr = [gsr_results[noise].get(genre, 0) for noise in noise_levels]
        plt.plot(noise_levels, genre_gsr, marker="o", label=genre)

    plt.xlabel("Noise Level (%)")
    plt.ylabel("GSR")
    plt.title("GSR Sensitivity by Genre")
    plt.legend()
    plt.grid(True)
    plt.savefig(os.path.join(output_dir, "gsr_sensitivity_by_genre.png"))

    print(f"Results saved to {output_dir}")

    return noise_levels, avg_gsr_results


if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.abspath(os.path.join(script_dir, "../../database/folkroot.db"))

    # Set seed for reproducibility
    random.seed(42)
    np.random.seed(42)

    test_gsr_sensitivity(db_path)
