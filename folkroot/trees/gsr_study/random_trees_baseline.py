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
  Script to generate a baseline for GSR (Genre Separation Ratio)
  using random phylogenetic trees.
  
  This script builds multiple random trees and calculates the GSR distribution
  to establish what values would be expected by pure chance.
"""

import os
import sys
import random
import time
import argparse
from multiprocessing import Pool, cpu_count
import numpy as np
import matplotlib.pyplot as plt
import dendropy
from tqdm import tqdm

# Import necessary functions
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from trees_utils import connect_database
from analysis_utils.metrics_analysis import calculate_genre_separation_ratio


def get_all_scores_with_genres(db_path):
    """Get all scores with their genres from the database"""
    db_conn = connect_database(db_path)
    cursor = db_conn.cursor()
    cursor.execute("SELECT score_id, genre FROM Score")
    genres_map = {row[0]: row[1] for row in cursor.fetchall()}
    db_conn.close()
    return genres_map


def generate_random_distance_matrix(n_scores, min_dist=0.5, max_dist=2.0):
    """
    Generate a random symmetric distance matrix.

    Args:
        n_scores (int): Number of scores (matrix size)
        min_dist (float): Minimum distance
        max_dist (float): Maximum distance

    Returns:
        numpy.ndarray: Random symmetric distance matrix
    """
    # Initialize zero matrix
    matrix = np.zeros((n_scores, n_scores))

    # Fill upper triangular with random distances
    for i in range(n_scores):
        for j in range(i + 1, n_scores):
            # Generate random distance
            dist = random.uniform(min_dist, max_dist)
            # Assign symmetrically
            matrix[i, j] = dist
            matrix[j, i] = dist

    return matrix


def build_tree_from_random_matrix(args):
    """
    Build a random phylogenetic tree and calculate its GSR.
    This function is designed to be executed in parallel.
    """
    iteration, db_path, score_ids, genres_map, output_base_dir = args

    try:
        # Create directory for this iteration with retry mechanism
        iter_dir = os.path.join(output_base_dir, f"iteration_{iteration}")
        retry_count = 0
        max_retries = 3

        while retry_count < max_retries:
            try:
                os.makedirs(iter_dir, exist_ok=True)
                break
            except OSError as e:
                retry_count += 1
                if retry_count == max_retries:
                    raise
                time.sleep(0.2)  # Add small delay before retrying

        # Generate random distance matrix
        n_scores = len(score_ids)
        distance_matrix = generate_random_distance_matrix(n_scores)

        # Create node labels (compatible with extract_score_id)
        labels = [
            f"{score_id}_{genres_map[score_id]}_random.krn" for score_id in score_ids
        ]

        # Save matrix as temporary CSV with unique filename to avoid conflicts
        temp_csv_path = os.path.join(iter_dir, f"distance_matrix_{iteration}.csv")
        with open(temp_csv_path, "w") as f:
            f.write("," + ",".join(labels) + "\n")
            for i, label in enumerate(labels):
                row = [label] + [str(distance_matrix[i, j]) for j in range(n_scores)]
                f.write(",".join(row) + "\n")

        # Read matrix with dendropy
        with open(temp_csv_path, "r") as f:
            pdm = dendropy.PhylogeneticDistanceMatrix.from_csv(
                src=f,
                delimiter=",",
            )

        # Generate tree with Neighbor Joining with fallback to UPGMA
        try:
            tree = pdm.nj_tree()
            if tree is None:
                raise ValueError("NJ tree generation returned None")
        except Exception as e:
            print(f"Warning in iteration {iteration}: Falling back to UPGMA: {str(e)}")
            tree = pdm.upgma_tree()
            if tree is None:
                raise ValueError("UPGMA fallback also failed")

        # Save tree in NEXUS format
        nexus_path = os.path.join(iter_dir, "random_tree.nexus")
        tree.write(
            path=nexus_path,
            schema="nexus",
            suppress_rooting=True,
            unquoted_underscores=True,
            store_tree_weights=True,
        )

        if not os.path.exists(nexus_path):
            raise FileNotFoundError(f"Failed to create nexus file: {nexus_path}")

        # Calculate GSR for this tree
        gsr_values = calculate_genre_separation_ratio(nexus_path, db_path)

        results_path = os.path.join(iter_dir, "gsr_results.txt")
        with open(results_path, "w") as f:
            for genre, gsr in sorted(gsr_values.items()):
                f.write(f"{genre}: {gsr}\n")

        return iteration, gsr_values

    except Exception as e:
        print(f"Error in iteration {iteration}: {str(e)}")
        return None


def analyze_random_trees_baseline(db_path, n_iterations=1000, n_processes=None):
    """
    Generate a GSR baseline from random trees.

    Args:
        db_path (str): Path to SQLite database
        n_iterations (int): Number of random trees to generate
        n_processes (int): Number of processes for parallelization (None=auto)

    Returns:
        dict: Dictionary with GSR statistics by genre
    """
    start_time = time.time()
    print(f"Generating random tree baseline with {n_iterations} iterations...")

    # Determine number of processes
    if n_processes is None:
        n_processes = max(1, cpu_count() - 1)  # Leave one core free
    print(f"Using {n_processes} parallel processes")

    # Get data from database
    genres_map = get_all_scores_with_genres(db_path)
    score_ids = list(genres_map.keys())
    genres = sorted(set(genres_map.values()))

    # Create directory for results
    output_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "random_trees_baseline"
    )
    os.makedirs(output_dir, exist_ok=True)

    # Prepare arguments for parallel processing
    args_list = [
        (i, db_path, score_ids, genres_map, output_dir) for i in range(n_iterations)
    ]

    # Execute in parallel
    gsr_by_genre = {genre: [] for genre in genres}

    with Pool(processes=n_processes) as pool:
        for result in tqdm(
            pool.imap_unordered(build_tree_from_random_matrix, args_list),
            total=n_iterations,
            desc="Processing random trees",
        ):
            if result is not None:
                iteration, gsr_values = result
                # Accumulate valid results
                for genre, gsr in gsr_values.items():
                    if not np.isnan(gsr) and not np.isinf(gsr):
                        gsr_by_genre[genre].append(gsr)

    # Calculate statistics by genre
    gsr_stats = {}
    for genre, values in gsr_by_genre.items():
        if values:
            gsr_stats[genre] = {
                "count": len(values),
                "mean": np.mean(values),
                "std": np.std(values),
                "median": np.median(values),
                "p25": np.percentile(values, 25),
                "p75": np.percentile(values, 75),
                "min": np.min(values),
                "max": np.max(values),
            }

    # Save statistics to CSV file
    stats_path = os.path.join(output_dir, "gsr_random_stats.csv")
    with open(stats_path, "w") as f:
        f.write("genre,count,mean,std,median,p25,p75,min,max\n")
        for genre, stats in sorted(gsr_stats.items()):
            values = [
                str(stats[key])
                for key in [
                    "count",
                    "mean",
                    "std",
                    "median",
                    "p25",
                    "p75",
                    "min",
                    "max",
                ]
            ]
            f.write(f"{genre},{','.join(values)}\n")

    # Generate visualizations
    visualize_random_baseline(gsr_by_genre, gsr_stats, output_dir)

    elapsed_time = time.time() - start_time
    print(f"Analysis completed in {elapsed_time:.2f} seconds")
    print(f"Results saved in: {output_dir}")

    return gsr_stats


def visualize_random_baseline(gsr_by_genre, gsr_stats, output_dir):
    """
    Visualize results from the random trees baseline.

    Args:
        gsr_by_genre (dict): GSR values by genre
        gsr_stats (dict): Calculated statistics by genre
        output_dir (str): Directory to save visualizations
    """
    # 1. Basic statistics by genre chart
    genres = list(gsr_stats.keys())

    plt.figure(figsize=(12, 8))

    # Prepare data for the chart
    x = np.arange(len(genres))
    means = [gsr_stats[g]["mean"] for g in genres]
    medians = [gsr_stats[g]["median"] for g in genres]

    # Create bar chart
    width = 0.35
    plt.bar(x - width / 2, means, width, label="Mean", color="steelblue", alpha=0.7)
    plt.bar(
        x + width / 2, medians, width, label="Median", color="lightcoral", alpha=0.7
    )

    # Add error bars for interquartile range
    for i, genre in enumerate(genres):
        plt.plot(
            [i, i],
            [gsr_stats[genre]["p25"], gsr_stats[genre]["p75"]],
            color="black",
            linestyle="-",
            linewidth=2,
        )

    # Configure chart
    plt.xlabel("Genre")
    plt.ylabel("GSR in random trees")
    plt.title("GSR Distribution in random trees by genre")
    plt.xticks(x, genres, rotation=45, ha="right")
    plt.legend()
    plt.grid(True, linestyle="--", alpha=0.7)
    plt.tight_layout()

    # Save chart
    plt.savefig(os.path.join(output_dir, "random_baseline_stats.png"))

    # 2. Distribution histograms by genre
    n_genres = len(genres)
    n_cols = min(3, n_genres)
    n_rows = (n_genres + n_cols - 1) // n_cols

    plt.figure(figsize=(15, 3 * n_rows))

    for i, genre in enumerate(genres):
        plt.subplot(n_rows, n_cols, i + 1)
        plt.hist(gsr_by_genre[genre], bins=20, color="steelblue", alpha=0.7)
        plt.axvline(
            gsr_stats[genre]["mean"],
            color="red",
            linestyle="--",
            linewidth=2,
            label="Mean",
        )
        plt.axvline(
            gsr_stats[genre]["median"],
            color="green",
            linestyle="-.",
            linewidth=2,
            label="Median",
        )
        plt.title(f"GSR Distribution for {genre}")
        plt.xlabel("GSR")
        plt.ylabel("Frequency")
        plt.grid(True, alpha=0.3)
        plt.legend()

    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "random_baseline_histograms.png"))

    # 3. Comparative boxplot
    plt.figure(figsize=(12, 6))

    # Prepare data for boxplot
    data = [gsr_by_genre[genre] for genre in genres]

    plt.boxplot(data, labels=genres)
    plt.title("GSR Comparison by genre in random trees")
    plt.ylabel("GSR")
    plt.grid(True, linestyle="--", alpha=0.7)
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()

    plt.savefig(os.path.join(output_dir, "random_baseline_boxplot.png"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate a GSR baseline using random trees."
    )
    parser.add_argument(
        "-n",
        "--iterations",
        type=int,
        default=1000,
        help="Number of random trees to generate (default: 1000)",
    )
    parser.add_argument(
        "-p",
        "--processes",
        type=int,
        default=None,
        help="Number of parallel processes (default: available cores - 1)",
    )
    parser.add_argument(
        "-d",
        "--database",
        type=str,
        default=None,
        help="Path to database (default: standard path)",
    )

    args = parser.parse_args()

    if args.database:
        db_path = args.database
    else:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        db_path = os.path.abspath(
            os.path.join(script_dir, "../../database/folkroot.db")
        )

    # Set seed for reproducibility
    random.seed(42)
    np.random.seed(42)

    analyze_random_trees_baseline(
        db_path=db_path, n_iterations=args.iterations, n_processes=args.processes
    )
