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
 # This script performs clustering of segments for all feature types:
 #  1. Runs qt_segments_clustering.py for each feature type to create cluster assignments
 #  2. Runs transfer_clusters_to_db.py to store the cluster assignments in the database
 #  3. Optionally, runs additional analysis and visualization scripts if the -v flag is set
 #
 # The supported feature types are:
 #  - diatonic
 #  - chromatic
 #  - rhythmic
 #  - diatonic_rhythmic
 #  - chromatic_rhythmic
'

#!/bin/bash

# Directory where the current script is located
script_dir=$(dirname "$(realpath "$0")")

# Define feature types to process
features=("diatonic" "chromatic" "rhythmic" "diatonic_rhythmic" "chromatic_rhythmic")

# Parse command line arguments
VISUALIZE=false

while getopts "v" opt; do
    case $opt in
    v)
        VISUALIZE=true
        ;;
    \?)
        echo "Invalid option: -$OPTARG" >&2
        exit 1
        ;;
    esac
done

# Function to run Python scripts and check for success
run_python_script() {
    local script_path="$1"
    local script_name=$(basename "$script_path")
    local args="$2"

    echo "Running $script_name $args..."
    python3 "$script_path" $args

    # Check if the previous script executed successfully
    if [ $? -ne 0 ]; then
        echo "Error running $script_name with args: $args"
        exit 1
    fi

    echo -e "$script_name execution completed successfully.\n"
}

# Step 1: Run clustering for each feature type
echo "Starting segment clustering for all feature types..."
echo "======================================================================================"
for feature in "${features[@]}"; do
    echo "Processing clustering for feature: $feature"
    echo "--------------------------------------------------------------------------------------"

    # Build arguments based on visualization flag
    args="-f $feature"
    if [ "$VISUALIZE" = true ]; then
        args="$args -v -pdf"
    fi

    run_python_script "$script_dir/qt_segments_clustering.py" "$args"
    echo "--------------------------------------------------------------------------------------"
done
echo "======================================================================================"
echo -e "Segment clustering completed for all feature types.\n"

# Step 2: Transfer clustering results to database
echo "Starting transfer of cluster data to database..."
echo "======================================================================================"
run_python_script "$script_dir/transfer_clusters_to_db.py" "-f all"
echo "======================================================================================"
echo -e "Transfer of cluster data to database completed.\n"

# Step 3: Additional analysis if visualization flag is set
if [ "$VISUALIZE" = true ]; then
    echo "Starting additional analysis and visualization..."
    echo "======================================================================================"

    # Run feature distribution analysis
    echo "Analyzing feature distributions..."
    run_python_script "$script_dir/analyze_features_distribution.py" ""

    # Run clustering analysis
    echo "Analyzing clustering results..."
    run_python_script "$script_dir/analyze_clustering.py" ""

    echo "======================================================================================"
    echo -e "Additional analysis and visualization completed.\n"
fi

echo "All operations completed successfully."
