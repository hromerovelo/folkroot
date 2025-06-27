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

#include "shared_segments_alignment.hpp"
#include <map>
#include <cmath>
#include <iomanip>

using namespace std;

/**
 * @brief Gets a map of segment group occurrences for a score and feature type.
 *        The map is keyed by group ID and contains the occurrence count.
 *
 * @param db Database connection
 * @param score_id Score ID to query
 * @param feature_type Feature type (e.g., "diatonic", "chromatic")
 * @return map<int, int> Map of group ID to occurrence count
 */
map<int, int> get_group_occurrences(sqlite3 *db, int score_id, const string &feature_type)
{
    map<int, int> group_counts;

    const char *sql =
        "SELECT stg.group_id "
        "FROM Segment s "
        "JOIN SegmentToGroup stg ON s.segment_id = stg.segment_id "
        "WHERE s.score_id = ? AND stg.feature_type = ? "
        "ORDER BY s.start_note ASC";

    sqlite3_stmt *stmt;
    if (sqlite3_prepare_v2(db, sql, -1, &stmt, nullptr) != SQLITE_OK)
    {
        cerr << "Failed to prepare statement for group occurrences: " << sqlite3_errmsg(db) << endl;
        return group_counts;
    }

    sqlite3_bind_int(stmt, 1, score_id);
    sqlite3_bind_text(stmt, 2, feature_type.c_str(), -1, SQLITE_STATIC);

    while (sqlite3_step(stmt) == SQLITE_ROW)
    {
        int group_id = sqlite3_column_int(stmt, 0);
        group_counts[group_id]++;
    }

    sqlite3_finalize(stmt);
    return group_counts;
}

/**
 * @brief Finds the maximum group ID across all scores for a feature type.
 *
 * @param db Database connection
 * @param feature_type Feature type (e.g., "diatonic", "chromatic")
 * @return int Maximum group ID
 */
int get_max_group_id(sqlite3 *db, const string &feature_type)
{
    int max_group_id = 0;

    const char *sql = "SELECT MAX(group_id) FROM SegmentToGroup WHERE feature_type = ?";

    sqlite3_stmt *stmt;
    if (sqlite3_prepare_v2(db, sql, -1, &stmt, nullptr) != SQLITE_OK)
    {
        cerr << "Failed to prepare statement for max group ID: " << sqlite3_errmsg(db) << endl;
        return 0;
    }

    sqlite3_bind_text(stmt, 1, feature_type.c_str(), -1, SQLITE_STATIC);

    if (sqlite3_step(stmt) == SQLITE_ROW && sqlite3_column_type(stmt, 0) != SQLITE_NULL)
    {
        max_group_id = sqlite3_column_int(stmt, 0);
    }

    sqlite3_finalize(stmt);
    return max_group_id;
}

/**
 * @brief Converts a map of group occurrences to a normalized vector.
 *
 * The vector will have a size of max_group_id + 1, with each element
 * representing the occurrence count for that group ID.
 *
 * @param occurrences Map of group ID to occurrence count
 * @param max_group_id Maximum group ID
 * @return vector<double> Normalized vector of group occurrences
 */
vector<double> map_to_vector(const map<int, int> &occurrences, int max_group_id)
{
    // Create a vector of size max_group_id + 1 to include group_id 0
    vector<double> result(max_group_id + 1, 0.0);

    // Fill in the vector with occurrence counts
    for (const auto &[group_id, count] : occurrences)
    {
        if (group_id <= max_group_id)
        {
            result[group_id] = static_cast<double>(count);
        }
    }

    return result;
}

/**
 * @brief Calculates the Euclidean distance between two vectors.
 *
 * The vectors can have different lengths, in which case the remaining
 * elements are squared and added to the sum.
 *
 * @param v1 First vector
 * @param v2 Second vector
 * @return double Euclidean distance between the vectors
 */
double euclidean_distance(const vector<double> &v1, const vector<double> &v2)
{
    double sum_sq = 0.0;
    size_t n = min(v1.size(), v2.size());

    for (size_t i = 0; i < n; i++)
    {
        double diff = v1[i] - v2[i];
        sum_sq += diff * diff;
    }

    // Handle case where vectors have different lengths
    if (v1.size() > n)
    {
        for (size_t i = n; i < v1.size(); i++)
        {
            sum_sq += v1[i] * v1[i];
        }
    }
    else if (v2.size() > n)
    {
        for (size_t i = n; i < v2.size(); i++)
        {
            sum_sq += v2[i] * v2[i];
        }
    }

    return sqrt(sum_sq);
}

/**
 * @brief Processes shared segment alignments between scores.
 *
 * Instead of using global alignment, this function compares scores based on
 * how many segments of each group they share, using Euclidean distance.
 * Lower distances indicate more similarity in segment group distributions.
 *
 * This function processes alignments for all possible score pairs, storing
 * the results in the database.
 *
 * @param db Database connection for storing results
 * @param level Alignment level (should be "shared_segments")
 */
void process_shared_segments_alignments(sqlite3 *db, const string &level)
{
    vector<int> scores = get_all_score_ids(db);
    size_t total_comparisons = (scores.size() * (scores.size() - 1)) / 2;
    size_t current_comparison = 0;
    const size_t PROGRESS_INTERVAL = 100;
    const size_t BATCH_SIZE = 10000;
    vector<AlignmentScores> batch;

    // Feature types to process
    vector<string> feature_types = {
        "diatonic", "chromatic", "rhythmic", "diatonic_rhythmic", "chromatic_rhythmic"};

    // Get max group IDs for each feature type
    map<string, int> max_group_ids;
    for (const auto &feature_type : feature_types)
    {
        max_group_ids[feature_type] = get_max_group_id(db, feature_type);
        cout << "Max group ID for " << feature_type << ": " << max_group_ids[feature_type] << endl;
    }

    // Cache the group occurrences for each score and feature type
    cout << "Building group occurrence cache for each score..." << endl;
    map<pair<int, string>, map<int, int>> cached_occurrences;
    for (int score_id : scores)
    {
        for (const auto &feature_type : feature_types)
        {
            cached_occurrences[{score_id, feature_type}] = get_group_occurrences(db, score_id, feature_type);
        }
    }
    cout << "Cache built successfully." << endl;

    // Process all score pairs
    for (size_t i = 0; i < scores.size(); i++)
    {
        for (size_t j = i + 1; j < scores.size(); j++)
        {
            current_comparison++;

            if (current_comparison % PROGRESS_INTERVAL == 0)
            {
                cout << "\rProgress: " << current_comparison << "/" << total_comparisons
                     << " comparisons (" << fixed << setprecision(2)
                     << (current_comparison * 100.0 / total_comparisons) << "%)" << flush;
            }

            AlignmentScores scores_result;
            scores_result.id1 = scores[i];
            scores_result.id2 = scores[j];
            scores_result.level = level;

            // Calculate distances for each feature type
            for (const auto &feature_type : feature_types)
            {
                int max_group_id = max_group_ids[feature_type];

                // Get group occurrence vectors for both scores
                vector<double> vector1 = map_to_vector(cached_occurrences[{scores[i], feature_type}], max_group_id);
                vector<double> vector2 = map_to_vector(cached_occurrences[{scores[j], feature_type}], max_group_id);

                // Calculate Euclidean distance
                double distance = euclidean_distance(vector1, vector2);

                // Store the distance as an integer (scaled by 100)
                int distance_score = static_cast<int>(round(distance * 100)); // Scale by 100 to preserve precision

                // Assign to appropriate score field
                if (feature_type == "diatonic")
                {
                    scores_result.diatonic_score = distance_score;
                }
                else if (feature_type == "chromatic")
                {
                    scores_result.chromatic_score = distance_score;
                }
                else if (feature_type == "rhythmic")
                {
                    scores_result.rhythmic_score = distance_score;
                }
                else if (feature_type == "diatonic_rhythmic")
                {
                    scores_result.diatonic_rhythmic_score = distance_score;
                }
                else if (feature_type == "chromatic_rhythmic")
                {
                    scores_result.chromatic_rhythmic_score = distance_score;
                }
            }

            batch.push_back(scores_result);

            if (batch.size() >= BATCH_SIZE)
            {
                save_alignments_batch(db, batch, false); // false because these are score alignments
                batch.clear();
                sqlite3_exec(db, "COMMIT", nullptr, nullptr, nullptr);
                sqlite3_exec(db, "BEGIN TRANSACTION", nullptr, nullptr, nullptr);
            }
        }
    }

    if (!batch.empty())
    {
        save_alignments_batch(db, batch, false);
    }

    cout << "\rProgress: " << total_comparisons << "/" << total_comparisons
         << " comparisons (100.00%)\n"
         << endl;
}