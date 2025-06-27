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
  Compare two genre distance heatmaps and calculate their correlation.
  
  This script loads distance matrices from Excel files generated
  by analyze_genre_distances.py and calculates various correlation metrics
  between them. Can compare either normalized or original distance matrices.
"""

import os
import argparse
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from scipy.stats import pearsonr, spearmanr, kendalltau
import re
import sys


def extract_level_feature(filename):
    """Extract level and feature from Excel filename."""
    # Example: genre_distances_note_diatonic.xlsx -> note, diatonic
    match = re.search(r"genre_distances_([^_]+)_(.+)\.xlsx", os.path.basename(filename))
    if match:
        return match.group(1), match.group(2)
    return None, None


def load_distance_matrix(excel_path, use_original=False):
    """Load distance matrix from Excel file.

    Args:
        excel_path: Path to Excel file
        use_original: If True, load from Distances_Original sheet, otherwise from Distances_Normalized
    """
    try:
        # Choose which sheet to load based on use_original flag
        sheet_name = "Distances_Original" if use_original else "Distances_Normalized"
        matrix = pd.read_excel(excel_path, sheet_name=sheet_name, index_col=0)
        return matrix
    except Exception as e:
        print(f"Error loading matrix from {excel_path} (sheet: {sheet_name}): {e}")
        return None


def compare_matrices(matrix1, matrix2):
    """Calculate correlation between two distance matrices."""
    # Get common genres
    common_genres = sorted(set(matrix1.index).intersection(set(matrix2.index)))

    if len(common_genres) < 2:
        print("Error: Matrices have fewer than 2 common genres.")
        return None

    # Filter matrices to use only common genres
    m1 = matrix1.loc[common_genres, common_genres]
    m2 = matrix2.loc[common_genres, common_genres]

    # Flatten the matrices (upper triangular only to avoid counting pairs twice)
    n = len(common_genres)
    flat1 = []
    flat2 = []

    for i in range(n):
        for j in range(i + 1, n):
            flat1.append(m1.iloc[i, j])
            flat2.append(m2.iloc[i, j])

    # Calculate correlations
    correlations = {
        "pearson": pearsonr(flat1, flat2),
        "spearman": spearmanr(flat1, flat2),
        "kendall": kendalltau(flat1, flat2),
    }

    return {
        "correlations": correlations,
        "common_genres": common_genres,
        "values1": flat1,
        "values2": flat2,
    }


def visualize_correlation(
    results, matrix1_name, matrix2_name, output_path=None, is_original=False
):
    """Create visualization of matrix correlation."""
    corr_values = results["correlations"]

    # Create figure with two subplots
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 7))

    # 1. Scatter plot of matrix values
    ax1.scatter(results["values1"], results["values2"], alpha=0.6)
    ax1.set_xlabel(f"{matrix1_name} Distance", fontsize=12, weight="bold")
    ax1.set_ylabel(f"{matrix2_name} Distance", fontsize=12, weight="bold")
    ax1.set_title("Distance Value Comparison", fontsize=14, weight="bold")

    # Add regression line
    z = np.polyfit(results["values1"], results["values2"], 1)
    p = np.poly1d(z)
    ax1.plot(
        sorted(results["values1"]), p(sorted(results["values1"])), "r--", linewidth=2
    )

    # 2. Bar chart of correlation coefficients
    correlation_values = [
        corr_values["pearson"][0],
        corr_values["spearman"][0],
        corr_values["kendall"][0],
    ]

    bars = ax2.bar(["Pearson", "Spearman", "Kendall"], correlation_values)

    # Add value labels on top of bars
    for bar in bars:
        height = bar.get_height()
        value = height if height >= 0 else height - 0.05
        ax2.text(
            bar.get_x() + bar.get_width() / 2.0,
            value,
            f"{height:.3f}",
            ha="center",
            va="bottom" if height >= 0 else "top",
            fontsize=12,
            weight="bold",
        )

    ax2.set_ylim(-1.05, 1.05)
    ax2.set_title("Correlation Coefficients", fontsize=14, weight="bold")
    ax2.set_ylabel("Correlation Value", fontsize=12, weight="bold")

    # Add description of the number of genres
    data_type = "original (non-normalized)" if is_original else "normalized"
    plt.figtext(
        0.5,
        0.01,
        f"Comparison based on {len(results['common_genres'])} common genres using {data_type} distances",
        ha="center",
        fontsize=12,
        weight="bold",
    )

    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    plt.suptitle(
        f"Correlation Analysis: {matrix1_name} vs {matrix2_name}",
        fontsize=16,
        weight="bold",
    )

    if output_path:
        plt.savefig(output_path, dpi=300, bbox_inches="tight")
        print(f"Correlation visualization saved to {output_path}")
    else:
        plt.show()


def format_name(level, feature):
    """Format level and feature for display."""
    # Format level
    if level == "note":
        level = "Global"
    elif "s25_ss75" in level:
        level = "F25_S75"
    elif "s50_ss50" in level:
        level = "F50_S50"
    elif "s75_ss25" in level:
        level = "F75_S25"
    else:
        level = level.replace("_", " ").title()

    # Format feature
    feature = feature.replace("_", "-").title()

    return f"{feature} ({level})"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compare two genre distance matrices")
    parser.add_argument("matrix1", help="Path to first matrix Excel file")
    parser.add_argument("matrix2", help="Path to second matrix Excel file")
    parser.add_argument(
        "--output", "-o", help="Output path for correlation visualization"
    )
    parser.add_argument(
        "--original",
        "-orig",
        action="store_true",
        help="Use original (non-normalized) distance matrices instead of normalized ones",
    )

    args = parser.parse_args()

    # Load matrices based on flag
    matrix1 = load_distance_matrix(args.matrix1, use_original=args.original)
    matrix2 = load_distance_matrix(args.matrix2, use_original=args.original)

    if matrix1 is None or matrix2 is None:
        print("Failed to load one or both matrices.")
        sys.exit(1)

    # Extract level and feature for display names
    level1, feature1 = extract_level_feature(args.matrix1)
    level2, feature2 = extract_level_feature(args.matrix2)

    matrix1_name = format_name(level1, feature1)
    matrix2_name = format_name(level2, feature2)

    results = compare_matrices(matrix1, matrix2)

    if results:
        # Print correlation results
        matrix_type = "original" if args.original else "normalized"
        pearson, p_value = results["correlations"]["pearson"]
        print(
            f"\nCorrelation Results ({len(results['common_genres'])} common genres, {matrix_type} matrices):"
        )
        print(f"Pearson correlation: {pearson:.4f} (p-value: {p_value:.4e})")
        print(f"Spearman correlation: {results['correlations']['spearman'][0]:.4f}")
        print(f"Kendall correlation: {results['correlations']['kendall'][0]:.4f}")

        # Create output path if not specified
        if not args.output:
            matrix1_base = os.path.splitext(os.path.basename(args.matrix1))[0]
            matrix2_base = os.path.splitext(os.path.basename(args.matrix2))[0]
            output_dir = os.path.dirname(args.matrix1)
            matrix_suffix = "_original" if args.original else "_normalized"
            args.output = os.path.join(
                output_dir,
                f"correlation_{matrix1_base}_vs_{matrix2_base}{matrix_suffix}.png",
            )

        visualize_correlation(
            results, matrix1_name, matrix2_name, args.output, is_original=args.original
        )
