: '
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
 '

: '
 # Created by Hilda Romero-Velo on March 2025.
 '

: '
 # This script generates phylogenetic trees for all combinations of:
 #  1. Features (diatonic, chromatic, rhythmic, diatonic_rhythmic, chromatic_rhythmic)
 #  2. Levels (note, structure, shared_segments, combined)
 #  3. Different genre groups:
 #     - All genres
 #     - Group 1: polca, polka, valse, waltz
 #     - Group 2: march, marchas, mazurka, mazurcas
 #     - Group N: (add more groups as needed)
 #  4. Different weights for combined level (0.25, 0.5, 0.75)
'
#!/bin/bash

# Directory where the current script is located
script_dir=$(dirname "$(realpath "$0")")

# Configuration variables
PYTHON_CMD="python3"
SCRIPT_PATH="$script_dir/generate_phylo_tree.py"

# Available features and levels
FEATURES=("diatonic" "chromatic" "rhythmic" "diatonic_rhythmic" "chromatic_rhythmic")
LEVELS=("note" "structure" "shared_segments" "combined")
WEIGHTS=("0.25" "0.5" "0.75")

# Define genre groups
declare -A GENRE_GROUPS
#GENRE_GROUPS[0]="polca polka valse waltz"
#GENRE_GROUPS[1]="march marchas mazurka mazurcas"

# Function to generate a tree
generate_tree() {
    local feature=$1
    local level=$2
    local genres=$3
    local genre_label=$4
    local structure_weight=$5

    # Build command
    local cmd="$PYTHON_CMD $SCRIPT_PATH --feature $feature --level $level"

    # Add structure weight if level is combined
    if [ "$level" = "combined" ]; then
        cmd="$cmd --structure-weight $structure_weight"
    fi

    # Add genres if specified
    if [ -n "$genres" ]; then
        cmd="$cmd --genres $genres"
    fi

    # Execute command silently (only errors will show)
    eval $cmd >/dev/null

    # Check for success
    if [ $? -ne 0 ]; then
        echo "Error generating tree for feature=$feature, level=$level, genres=$genre_label"
        return 1
    fi

    return 0
}

# Function to generate a tree and analyze genre distances
generate_and_analyze_tree() {
    local feature=$1
    local level=$2
    local genres=$3
    local genre_label=$4
    local structure_weight=$5

    # Call generate_tree function
    generate_tree "$feature" "$level" "$genres" "$genre_label" "$structure_weight"
    if [ $? -ne 0 ]; then
        return 1
    fi

    # If this is an all_genres tree, run genre distance analysis
    if [ "$genre_label" = "all_genres" ]; then
        # Determine tree filename based on params
        if [ "$level" = "combined" ]; then
            structure_part=$(printf "%02d" $(echo "${structure_weight} * 100" | bc | cut -d. -f1))
            shared_part=$(printf "%02d" $(echo "100 - (${structure_weight} * 100)" | bc | cut -d. -f1))

            tree_dir="$script_dir/generated_trees/combined_level_s${structure_part}_ss${shared_part}"
            tree_name="combined_s${structure_part}_ss${shared_part}_${feature}_all_genres"
        else
            tree_dir="$script_dir/generated_trees/${level}_level"
            tree_name="${level}_level_${feature}_all_genres"
        fi

        tree_path="$tree_dir/${tree_name}/${tree_name}_phylogenetic_tree.nexus"

        if [ ! -f "$tree_path" ]; then
            echo "Warning: Tree file not found at expected location: $tree_path" >>"$script_dir/tree_errors.log"
        fi
    fi

    return 0
}

# Calculate total number of trees to generate
total_trees=0
for feature in "${FEATURES[@]}"; do
    for level in "${LEVELS[@]}"; do
        if [ "$level" = "combined" ]; then
            # 3 weights for each combined level
            total_trees=$((total_trees + 3))
        else
            total_trees=$((total_trees + 1))
        fi
    done
done

# Count how many genre groups are actually defined
num_genre_groups=0
for key in "${!GENRE_GROUPS[@]}"; do
    if [ -n "${GENRE_GROUPS[$key]}" ]; then
        num_genre_groups=$((num_genre_groups + 1))
    fi
done

# Save base tree count
base_trees=$total_trees

# Calculate total including group-specific trees (all_genres + specific groups)
total_trees=$((total_trees * (1 + num_genre_groups)))

# Add genre trees for the all_genres trees
genre_trees=$base_trees

# Get final total including genre trees
grand_total=$((total_trees + genre_trees))

echo "Starting generation of $total_trees phylogenetic trees plus $genre_trees genre trees..."
echo "Genre groups defined: $num_genre_groups"
echo "Total: $grand_total trees"
echo "==============================================="

# Counter for progress tracking
current_tree=0

# Part 1: Generate trees for all genres
echo "Generating trees for all genres..."

for feature in "${FEATURES[@]}"; do
    for level in "${LEVELS[@]}"; do
        # For combined level, generate with different weights
        if [ "$level" = "combined" ]; then
            for weight in "${WEIGHTS[@]}"; do
                current_tree=$((current_tree + 1))
                echo -ne "Progress: $current_tree/$grand_total trees ($(((current_tree * 100) / grand_total))%)\r"
                generate_and_analyze_tree "$feature" "$level" "" "all_genres" "$weight"
                # Count the genre tree as well when we complete the analysis
                current_tree=$((current_tree + 1))
            done
        else
            current_tree=$((current_tree + 1))
            echo -ne "Progress: $current_tree/$grand_total trees ($(((current_tree * 100) / grand_total))%)\r"
            generate_and_analyze_tree "$feature" "$level" "" "all_genres" ""
            # Count the genre tree as well when we complete the analysis
            current_tree=$((current_tree + 1))
        fi
    done
done

echo -e "\nAll-genres trees completed."
echo "==============================================="

# Part 2: Generate trees for specific genre groups
for group_index in "${!GENRE_GROUPS[@]}"; do
    genres="${GENRE_GROUPS[$group_index]}"
    group_name="Group $((group_index + 1))"

    echo "Generating trees for $group_name: $genres"

    for feature in "${FEATURES[@]}"; do
        for level in "${LEVELS[@]}"; do
            # For combined level, generate with different weights
            if [ "$level" = "combined" ]; then
                for weight in "${WEIGHTS[@]}"; do
                    current_tree=$((current_tree + 1))
                    echo -ne "Progress: $current_tree/$grand_total trees ($(((current_tree * 100) / grand_total))%)\r"
                    generate_tree "$feature" "$level" "$genres" "$group_name" "$weight"
                done
            else
                current_tree=$((current_tree + 1))
                echo -ne "Progress: $current_tree/$grand_total trees ($(((current_tree * 100) / grand_total))%)\r"
                generate_tree "$feature" "$level" "$genres" "$group_name" ""
            fi
        done
    done
    echo -e "\n$group_name trees completed."
    echo "==============================================="
done

echo "Generating metrics analysis for genre trees..."
$PYTHON_CMD "$script_dir/analyze_genre_distances.py" --directory "$script_dir/generated_trees" 2>>"$script_dir/genre_analysis_errors.log"

if [ $? -eq 0 ]; then
    echo "Metrics analysis completed successfully."
else
    echo "Warning: Error during metrics analysis. Check the log for details."
fi

echo "==============================================="

echo "Trees generation completed successfully."
