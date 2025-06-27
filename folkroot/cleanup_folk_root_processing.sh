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
 # This script deletes all directories and files created during the process of extracting
 # features from music scores and preparing data for alignment.
 '

#!/bin/bash

# Directory where the current script is located
script_dir=$(dirname "$(realpath "$0")")

# List of directories and files to be deleted, using absolute paths
paths_to_delete=(
  "$(realpath "$script_dir/data/computed")"                        # Directory with all computed features and processed score data
  "$(realpath "$script_dir/data/segments")"                        # Directory with all extracted segments from the scores
  "$(realpath "$script_dir/segments_and_features_computing/logs")" # Directory with log files generated during the process
  "$(realpath "$script_dir/database/folkroot.db")"                 # SQLite database file with extracted features and metadata
  "$(realpath "$script_dir/database/folkroot_db_error_log.txt")"   # Log file with errors during database creation
  "$(realpath "$script_dir/segments_clustering/results")"          # Directory with clustering results for segments
  "$(realpath "$script_dir/trees/generated_trees")"                # Directory with generated trees
  "$(realpath "$script_dir/trees/genre_analysis")"                 # Directory with genre analysis metrics
  "$(realpath "$script_dir/trees/tree_visualizations_pdf")"        # Directory with tree visualizations
)

# Notify the user that deletion is starting
echo "Deleting scores generated files and directories..."

# Loop through each path and delete if it exists
for path in "${paths_to_delete[@]}"; do
  # Check if the path exists (can be either a file or directory)
  if [ -e "$path" ]; then
    rm -rf "$path"                 # Delete directory or file recursively and forcefully
    echo "$path has been deleted." # Confirmation message
  fi
done

# Notify the user that cleanup is complete
echo "Scores cleanup completed."
