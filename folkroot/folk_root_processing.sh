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
 # This script executes the necessary processes to compute the scores and
 # segments features. It also generates the SQLite database with the extracted
 # data and optionally performs global alignment for segments or scores at the
 # selected level. 
 #
 # Usage: bash folk_root_processing.sh [OPTIONS]
 # 
 # Options:
 #   --alignment [segment|score|all|none]   Type of alignment to execute. Default: none.
 #   --level [note|structure|shared_segments|all]  Level of score alignment. Default: none. 
 #                                          Required when --alignment is score or all.
 #   --skip-setup                           Skip the database generation step.
 #   --skip-clustering                      Skip the segments clustering step.
 #   --visualize                            Generate visualizations for clustering
 #   --trees                                Generate phylogenetic trees and visualizations
 #
 # Example:
 #   bash folk_root_processing.sh --alignment all --level all 
 '

#!/bin/bash
set -e # Exit immediately if any command fails

# Current script directory
script_dir=$(dirname "$(realpath "$0")")

database_directory="$script_dir/database"

segments_clustering_directory="$script_dir/segments_clustering"

# Parse command-line arguments
alignment_type="none"
score_level="none"
skip_setup=false
skip_clustering=false
generate_visualizations=false
generate_trees=false

while [[ "$#" -gt 0 ]]; do
  case $1 in
  --alignment)
    alignment_type="$2"
    shift
    ;;
  --level)
    score_level="$2"
    shift
    ;;
  --skip-setup)
    skip_setup=true
    ;;
  --skip-clustering)
    skip_clustering=true
    ;;
  --visualize)
    generate_visualizations=true
    ;;
  --trees)
    generate_trees=true
    ;;
  *)
    echo "Unknown parameter passed: $1"
    exit 1
    ;;
  esac
  shift
done

# Validate level parameter when score or all alignment is requested
if [[ ("$alignment_type" == "score" || "$alignment_type" == "all") && "$score_level" == "none" ]]; then
  echo "Error: When --alignment is set to 'score' or 'all', --level must be specified."
  echo "Valid levels are: note, structure, shared_segments, all"
  exit 1
fi

# Check if clustering is required but skipped
clustering_required=false

if [[ "$alignment_type" == "score" && ("$score_level" == "structure" || "$score_level" == "shared_segments" || "$score_level" == "all") ]]; then
  clustering_required=true
elif [[ "$alignment_type" == "all" ]]; then
  clustering_required=true
fi

if [[ "$clustering_required" == true && "$skip_clustering" == true ]]; then
  echo "Warning: The selected alignment type and level typically require clustering."
  echo "You've chosen to skip clustering with the --skip-clustering option."
  echo "This is only appropriate if clustering has already been performed and is present in the database."
  echo ""
  read -p "Are you sure you want to continue without running clustering? (y/n): " confirm
  echo ""

  if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
    echo "Operation cancelled. Remove the --skip-clustering option to perform clustering automatically."
    exit 0
  else
    echo "Proceeding without clustering as requested."
  fi
fi

# If score alignment with structure or shared_segments level is requested, ensure segment alignment is run first
if [[ "$alignment_type" == "score" && ("$score_level" == "structure" || "$score_level" == "shared_segments" || "$score_level" == "all") && "$skip_clustering" == false ]]; then
  echo "Warning: The requested score alignment requires segment alignment and clustering to be performed first."
  echo "Running with --alignment all instead to ensure proper processing order."
  alignment_type="all"
fi

# Validate alignment_type
case $alignment_type in
segment)
  echo -e "Global alignment will be executed for segments.\n"
  ;;
score)
  if [[ "$score_level" != "note" && "$score_level" != "structure" && "$score_level" != "shared_segments" && "$score_level" != "all" ]]; then
    echo "Invalid level specified. Use 'note', 'structure', 'shared_segments' or 'all'."
    exit 1
  fi
  echo -e "Alignment will be executed for scores at $score_level level.\n"
  ;;
all)
  if [[ "$score_level" != "note" && "$score_level" != "structure" && "$score_level" != "shared_segments" && "$score_level" != "all" ]]; then
    echo "Invalid level specified. Use 'note', 'structure', 'shared_segments' or 'all'."
    exit 1
  fi
  echo -e "Global alignment will be executed for:"
  echo -e "- Segments"
  echo -e "- Scores at $score_level level\n"
  ;;
none)
  echo -e "Alignments will be skipped.\n"
  ;;
*)
  echo "Invalid alignment type specified. Use 'segment', 'score', 'all', or 'none'."
  exit 1
  ;;
esac

# Only execute setup steps if skip_setup is false
if [ "$skip_setup" = false ]; then
  # Generate the SQLite database
  echo -e "Generating database..."
  sqlite3 "$database_directory/folkroot.db" <"$database_directory/generate_database.sql"
  echo -e "Database generated successfully.\n\n"

  # Directory containing the scripts and Python files for computing features
  features_computing_directory="$script_dir/segments_and_features_computing"

  # Execute features computation script
  echo -e "Computing features...\n"
  bash "$features_computing_directory/compute_features.sh"
  echo -e "Features computed successfully.\n\n"
else
  echo -e "Skipping database generation and feature computation.\n"
fi

alignment_directory="$script_dir/features_alignment"

run_global_alignment() {
  local type=$1
  local level=$2

  echo -e "\n----------------------------------------"
  echo "Executing alignment:"
  echo "- Type: $type"
  [[ "$type" == "score" ]] && echo "- Level: $level"
  echo -e "----------------------------------------\n"

  g++ -o "$alignment_directory/compute_features_alignment" \
    "$alignment_directory/compute_features_alignment.cpp" \
    "$alignment_directory/utils/global_approximate_alignment.cpp" \
    "$alignment_directory/utils/shared_segments_alignment.cpp" \
    "$alignment_directory/utils/common.cpp" \
    -lsqlite3 -std=c++17

  if [ $? -eq 0 ]; then
    echo "Compilation successful, executing alignment..."
    cd "$alignment_directory"
    if [ "$type" = "score" ]; then
      ./compute_features_alignment --type=$type --level $level
    else
      ./compute_features_alignment --type=$type
    fi
    if [ $? -eq 0 ]; then
      echo -e "Alignment completed successfully.\n"
    else
      echo -e "Error: Failed to execute alignment.\n"
      exit 1
    fi
  else
    echo -e "Error: Failed to compile alignment code.\n"
    exit 1
  fi
  cd "$script_dir"
}

run_segments_clustering() {
  if [ "$skip_clustering" = true ]; then
    echo -e "Skipping segments clustering as requested.\n"
    return
  fi

  echo -e "\n=========================================================================="
  echo "Executing segments clustering for all feature types..."
  echo -e "==========================================================================\n"

  # Add visualizations flag if requested
  if [ "$generate_visualizations" = true ]; then
    bash "$segments_clustering_directory/undertake_segments_clustering.sh" -v
  else
    bash "$segments_clustering_directory/undertake_segments_clustering.sh"
  fi

  if [ $? -eq 0 ]; then
    echo -e "Segments clustering completed successfully.\n"
  else
    echo -e "Error: Failed to execute segments clustering.\n"
    exit 1
  fi
}

# Add function to generate phylogenetic trees
run_phylogenetic_analysis() {
  if [ "$generate_trees" = true ]; then
    echo -e "\n=========================================================================="
    echo "Generating phylogenetic trees..."
    echo -e "==========================================================================\n"

    # Generate trees
    bash "$script_dir/trees/generate_all_phylo_trees.sh"
    if [ $? -ne 0 ]; then
      echo "Error: Failed to generate phylogenetic trees."
      exit 1
    fi

    # Generate visualizations
    bash "$script_dir/trees/visualize_all_trees.sh"
    if [ $? -ne 0 ]; then
      echo "Error: Failed to generate tree visualizations."
      exit 1
    fi

    echo -e "Phylogenetic analysis completed successfully.\n"
  fi
}

# Execute alignment based on user selection
case $alignment_type in
segment)
  run_global_alignment "segment"
  run_segments_clustering
  ;;
score)
  if [ "$score_level" = "all" ]; then
    run_global_alignment "score" "note"
    run_global_alignment "score" "structure"
    run_global_alignment "score" "shared_segments"
  else
    run_global_alignment "score" "$score_level"
  fi
  ;;
all)
  # First run segment alignment
  run_global_alignment "segment"

  # Then run segments clustering
  run_segments_clustering

  # Finally run score alignments
  if [ "$score_level" = "all" ]; then
    run_global_alignment "score" "note"
    run_global_alignment "score" "structure"
    run_global_alignment "score" "shared_segments"
  else
    run_global_alignment "score" "$score_level"
  fi
  ;;
none)
  echo -e "Skipping alignments.\n"
  ;;
esac

# Add phylogenetic analysis execution at the end
run_phylogenetic_analysis

echo -e "Process completed successfully.\n"
