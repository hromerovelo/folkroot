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
 # This script runs the necessary scripts to extract the segments from the scores
 # and then:
 #  1. Extract the diatonic, chromatic, and rhythmic features of the scores.
 #  2. Extract the diatonic, chromatic, and rhythmic features of the segments.
 #  3. Process the extracted features of the scores and segments to save them in JSON files.
 #  4. Clean and combine the extracted features of the scores and segments to save them in the database.
 '

#!/bin/bash

# Directory where the current script is located
script_dir=$(dirname "$(realpath "$0")")

# Function to run bash scripts and check for success
run_script() {
    local script_path="$1"
    local script_name=$(basename "$script_path")
    local segment_flag="$2"
    if [ -z "$segment_flag" ]; then
        msg="for scores"
    else
        msg="for segments"
    fi
    echo "Running $script_name script $msg..."
    bash "$script_path" $segment_flag

    # Check if the previous script executed successfully
    if [ $? -ne 0 ]; then
        echo "Error running $script_name $msg."
        exit 1
    fi

    echo -e "$script_name execution completed $msg.\n"
}

# Function to run Python scripts and check for success
run_python_script() {
    local script_path="$1"
    local script_name=$(basename "$script_path")
    local segment_flag="$2"
    if [ -z "$segment_flag" ]; then
        msg="for scores"
    else
        msg="for segments"
    fi
    echo "Running $script_name script $msg..."
    python3 "$script_path" $segment_flag

    # Check if the previous script executed successfully
    if [ $? -ne 0 ]; then
        echo "Error running $script_name $msg."
        exit 1
    fi

    echo -e "$script_name execution completed $msg.\n"
}

# Execute the extraction of segments from the scores
echo "Extracting segments from scores..."
python3 "$script_dir/segments_scripts/extract_scores_segments.py"
if [ $? -ne 0 ]; then
    echo "Error extracting segments from scores."
    exit 1
fi
echo -e "Segments extraction completed.\n"

# Execute the script to extract diatonic, chromatic, and rhythmic features for scores and segments
run_script "$script_dir/features_scripts/extract_features.sh"
run_script "$script_dir/features_scripts/extract_features.sh" "--segment"

# Execute file to process the extracted features and save them in JSON files
run_python_script "$script_dir/features_scripts/process_features.py"
run_python_script "$script_dir/features_scripts/process_features.py" "--segment"

# Execute file to clean and combine the extracted features and save them in the database
run_python_script "$script_dir/features_scripts/set_features_values.py"
run_python_script "$script_dir/features_scripts/set_features_values.py" "--segment"
