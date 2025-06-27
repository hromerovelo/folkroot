/***
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
**/

//
// Created by Hilda Romero-Velo on March 2025.
//

#ifndef FOLKROOT_COMMON_HPP
#define FOLKROOT_COMMON_HPP

#include <sqlite3.h>
#include <string>
#include <vector>
#include <optional>
#include <iostream>

/**
 * @brief Represents the feature data for a segment or score.
 *
 * Contains the ID and feature vectors for different types of musical features
 * used in alignment calculations.
 */
struct FeatureData
{
  int id;                                                     ///< ID of the segment or score
  std::vector<std::optional<int>> diatonic_feature;           ///< Diatonic pitch feature
  std::vector<std::optional<int>> chromatic_feature;          ///< Chromatic pitch feature
  std::vector<std::optional<int>> rhythmic_feature;           ///< Rhythmic feature
  std::vector<std::optional<int>> diatonic_rhythmic_feature;  ///< Combined diatonic and rhythmic features
  std::vector<std::optional<int>> chromatic_rhythmic_feature; ///< Combined chromatic and rhythmic features
};

/**
 * @brief Represents the alignment scores between two segments or scores.
 *
 * Contains the IDs of the compared elements and their alignment scores
 * for different feature types.
 */
struct AlignmentScores
{
  int id1;                      ///< ID of the first segment/score
  int id2;                      ///< ID of the second segment/score
  std::string level;            ///< Alignment level (note/structure/shared_segments) for score alignments
  int diatonic_score;           ///< Alignment score for diatonic features
  int chromatic_score;          ///< Alignment score for chromatic features
  int rhythmic_score;           ///< Alignment score for rhythmic features
  int diatonic_rhythmic_score;  ///< Alignment score for combined diatonic and rhythmic features
  int chromatic_rhythmic_score; ///< Alignment score for combined chromatic and rhythmic features
};

/**
 * @brief Initializes and configures the SQLite database connection with optimized settings.
 *
 * Configures the database with WAL journaling, memory-optimized settings, and
 * begins a transaction. Settings are optimized for bulk insertions and high
 * performance on systems with sufficient RAM.
 *
 * @param db_path Path to the SQLite database file
 * @return sqlite3* Pointer to the initialized database connection, or nullptr if initialization fails
 */
sqlite3 *initialize_database(const std::string &db_path);

/**
 * @brief Saves a batch of alignment scores to the database.
 *
 * Performs batch insertion of alignment scores for either segments or scores.
 * Uses prepared statements for efficient insertion and handles the different
 * schema requirements for segment and score alignments.
 *
 * @param db Database connection to use for insertion
 * @param alignments Vector of alignment scores to insert
 * @param is_segment True if inserting segment alignments, false for score alignments
 */
void save_alignments_batch(sqlite3 *db, const std::vector<AlignmentScores> &alignments, bool is_segment);

/**
 * @brief Gets all score IDs from the database.
 *
 * @param db Database connection
 * @return std::vector<int> List of all score IDs
 */
std::vector<int> get_all_score_ids(sqlite3 *db);

#endif