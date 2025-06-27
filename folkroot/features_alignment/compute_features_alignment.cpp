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

#include <sqlite3.h>
#include <string>
#include <vector>
#include <iostream>
#include <cstring>
#include <iomanip>
#include <variant>
#include <optional>
#include <sstream>
#include "utils/common.hpp"
#include "utils/global_approximate_alignment.hpp"
#include "utils/shared_segments_alignment.hpp"

using namespace std;

/**
 * @brief Convert a string feature to a vector of optional integers.
 *
 * @param feature The string feature to be converted with values separated by ';'.
 *
 * @return vector<optional<int>> The vector of optional integers.
 */
vector<optional<int>> convert_feature_to_vector(const string &feature)
{
    vector<optional<int>> result;
    stringstream ss(feature);
    string value;

    while (getline(ss, value, ';'))
    {
        if (value.empty())
            continue;

        if (value == "r") // Melodic value for rest
        {
            result.push_back(nullopt);
        }
        else
        {
            try
            {
                result.push_back(stoi(value));
            }
            catch (const invalid_argument &e)
            {
                cerr << "Invalid value in feature: " << value << endl;
                result.push_back(nullopt);
            }
            catch (const out_of_range &e)
            {
                cerr << "Value out of range: " << value << endl;
                result.push_back(nullopt);
            }
        }
    }

    return result;
}

/**
 * @brief Get the structural feature of a score by type. The feature is a vector of group IDs
 *       for the segments in the score.
 *
 * @param db The SQLite database connection.
 * @param score_id The ID of the score.
 * @param feature_type Feature to retrieve (diatonic, chromatic, rhythmic, diatonic_rhythmic,
 *                  chromatic_rhythmic).
 *
 * @return vector<optional<int>> The vector of group IDs for the structural feature of the score
 *        for the given type.
 */
vector<optional<int>> get_structural_feature(sqlite3 *db, int score_id, const string &feature_type)
{
    vector<optional<int>> feature_groups;
    const char *sql =
        "SELECT stg.group_id "
        "FROM Segment s "
        "JOIN SegmentToGroup stg ON s.segment_id = stg.segment_id "
        "WHERE s.score_id = ? AND stg.feature_type = ? "
        "ORDER BY s.start_note ASC";

    sqlite3_stmt *stmt;
    if (sqlite3_prepare_v2(db, sql, -1, &stmt, nullptr) != SQLITE_OK)
    {
        cerr << "Failed to prepare statement for structural feature: " << sqlite3_errmsg(db) << endl;
        return feature_groups;
    }

    sqlite3_bind_int(stmt, 1, score_id);
    sqlite3_bind_text(stmt, 2, feature_type.c_str(), -1, SQLITE_STATIC);

    while (sqlite3_step(stmt) == SQLITE_ROW)
    {
        feature_groups.push_back(sqlite3_column_int(stmt, 0));
    }

    sqlite3_finalize(stmt);
    return feature_groups;
}

/**
 * @brief Get the necessary features for alignment from the database.
 *     If is_segment is true, segment features are retrieved; otherwise, score features are retrieved.
 *     If is_structure is true, the feature vectors are replaced by the group IDs of the segments
 *     in the score defining the structure of each score taking into account the feature type.
 *
 * @param db The SQLite database connection.
 * @param is_segment Flag to indicate if segment features are to be retrieved.
 * @param is_structure Flag to indicate if structural features are to be retrieved.
 *
 * @return vector<FeatureData> The vector of feature data retrieved from the database. It contains
 *        the ID of the segment or score and the feature vectors for diatonic, chromatic, rhythmic,
 *        diatonic_rhythmic, and chromatic_rhythmic features. The features are converted to vectors
 *        of optional integers, where nullopt represents rests ("r" values) in the melodic feature
 *        when combined with rhythmic values.
 */
vector<FeatureData> get_feature_data(sqlite3 *db, bool is_segment, bool is_structure)
{
    vector<FeatureData> data;
    const char *sql;

    if (is_segment)
    {
        sql = "SELECT segment_id, diatonic_feature, chromatic_feature, "
              "rhythmic_feature, diatonic_rhythmic_feature, chromatic_rhythmic_feature "
              "FROM Segment WHERE diatonic_feature != ''";
    }
    else if (is_structure)
    {
        sql = "SELECT DISTINCT score_id FROM Score";
    }
    else
    {
        sql = "SELECT score_id, diatonic_feature, chromatic_feature, "
              "rhythmic_feature, diatonic_rhythmic_feature, chromatic_rhythmic_feature "
              "FROM Score WHERE diatonic_feature != ''";
    }

    sqlite3_stmt *stmt;
    if (sqlite3_prepare_v2(db, sql, -1, &stmt, nullptr) != SQLITE_OK)
    {
        cerr << "Failed to prepare statement: " << sqlite3_errmsg(db) << endl;
        return data;
    }

    while (sqlite3_step(stmt) == SQLITE_ROW)
    {
        FeatureData fd;
        fd.id = sqlite3_column_int(stmt, 0);

        if (is_structure)
        {
            // For structural analysis, get group IDs of segments
            fd.diatonic_feature = get_structural_feature(db, fd.id, "diatonic");
            fd.chromatic_feature = get_structural_feature(db, fd.id, "chromatic");
            fd.rhythmic_feature = get_structural_feature(db, fd.id, "rhythmic");
            fd.diatonic_rhythmic_feature = get_structural_feature(db, fd.id, "diatonic_rhythmic");
            fd.chromatic_rhythmic_feature = get_structural_feature(db, fd.id, "chromatic_rhythmic");
        }
        else
        {
            // Convert string features to vectors of optional<int>
            const char *diatonic = (const char *)sqlite3_column_text(stmt, 1);
            const char *chromatic = (const char *)sqlite3_column_text(stmt, 2);
            const char *rhythmic = (const char *)sqlite3_column_text(stmt, 3);
            const char *diatonic_rhythmic = (const char *)sqlite3_column_text(stmt, 4);
            const char *chromatic_rhythmic = (const char *)sqlite3_column_text(stmt, 5);

            fd.diatonic_feature = convert_feature_to_vector(diatonic ? diatonic : "");
            fd.chromatic_feature = convert_feature_to_vector(chromatic ? chromatic : "");
            fd.rhythmic_feature = convert_feature_to_vector(rhythmic ? rhythmic : "");
            fd.diatonic_rhythmic_feature = convert_feature_to_vector(diatonic_rhythmic ? diatonic_rhythmic : "");
            fd.chromatic_rhythmic_feature = convert_feature_to_vector(chromatic_rhythmic ? chromatic_rhythmic : "");
        }

        data.push_back(fd);
    }

    sqlite3_finalize(stmt);
    return data;
}

/**
 * @brief Processes all pairwise alignments for the given feature data.
 *
 * Computes alignments between all pairs of elements (segments or scores)
 * for multiple feature types. Processes alignments in batches for efficiency
 * and displays progress information during execution.
 *
 * @param db Database connection for storing results
 * @param data Vector of feature data to align
 * @param is_segment True if processing segment alignments, false for score alignments
 * @param level Alignment level ('note' or 'structure') for score alignments
 */
void process_alignments(sqlite3 *db, const vector<FeatureData> &data,
                        bool is_segment, const string &level)
{
    size_t total_comparisons = (data.size() * (data.size() - 1)) / 2;
    size_t current_comparison = 0;
    const size_t PROGRESS_INTERVAL = 100;
    const size_t BATCH_SIZE = 10000;
    vector<AlignmentScores> batch;

    for (size_t i = 0; i < data.size(); i++)
    {
        for (size_t j = i + 1; j < data.size(); j++)
        {
            current_comparison++;

            if (current_comparison % PROGRESS_INTERVAL == 0)
            {
                cout << "\rProgress: " << current_comparison << "/" << total_comparisons
                     << " comparisons (" << fixed << setprecision(2)
                     << (current_comparison * 100.0 / total_comparisons) << "%)" << flush;
            }

            AlignmentScores scores;
            scores.id1 = data[i].id;
            scores.id2 = data[j].id;
            scores.level = level;

            scores.diatonic_score = global_alignment(
                data[i].diatonic_feature, data[j].diatonic_feature, 0, 1, 1);
            scores.chromatic_score = global_alignment(
                data[i].chromatic_feature, data[j].chromatic_feature, 0, 1, 1);
            scores.rhythmic_score = global_alignment(
                data[i].rhythmic_feature, data[j].rhythmic_feature, 0, 1, 1);
            scores.diatonic_rhythmic_score = global_alignment(
                data[i].diatonic_rhythmic_feature, data[j].diatonic_rhythmic_feature, 0, 1, 1);
            scores.chromatic_rhythmic_score = global_alignment(
                data[i].chromatic_rhythmic_feature, data[j].chromatic_rhythmic_feature, 0, 1, 1);

            batch.push_back(scores);

            if (batch.size() >= BATCH_SIZE)
            {
                save_alignments_batch(db, batch, is_segment);
                batch.clear();
                sqlite3_exec(db, "COMMIT", nullptr, nullptr, nullptr);
                sqlite3_exec(db, "BEGIN TRANSACTION", nullptr, nullptr, nullptr);
            }
        }
    }

    if (!batch.empty())
    {
        save_alignments_batch(db, batch, is_segment);
    }

    cout << "\rProgress: " << total_comparisons << "/" << total_comparisons
         << " comparisons (100.00%)\n"
         << endl;
}

/**
 * @brief Computes pairwise alignments between features stored in the database.
 *
 * This program performs two types of alignments:
 * 1. Segment alignment: Compares features between pairs of segments
 * 2. Score alignment: Compares features between pairs of scores at three levels:
 *    - Note level: Uses the actual feature values
 *    - Structure level: Uses segment group IDs to represent the score structure
 *    - Shared segments: Uses vectors of group occurrence counts and Euclidean distance
 *
 * For each pair, it computes alignments for five feature types:
 * - Diatonic
 * - Chromatic
 * - Rhythmic
 * - Diatonic-rhythmic combined
 * - Chromatic-rhythmic combined
 *
 * Usage:
 *   For segments: program --type=segment
 *   For scores:  program --type=score --level <note|structure|shared_segments>
 *
 * @param argc Number of command-line arguments
 * @param argv Array of command-line arguments
 * @return int 0 on success, 1 on error
 */
int main(int argc, char *argv[])
{
    if (argc < 2)
    {
        cerr << "Usage: " << argv[0] << " --type=[segment|score] [--level <level>]" << endl;
        cerr << "Note: --level is required when --type=score" << endl;
        cerr << "Level values must be 'note', 'structure', or 'shared_segments'" << endl;
        return 1;
    }

    bool is_segment = strcmp(argv[1], "--type=segment") == 0;
    string level = "";

    // Check and validate level parameter for score alignment
    if (!is_segment)
    {
        if (argc != 4 || strcmp(argv[2], "--level") != 0)
        {
            cerr << "Error: --level parameter is required for score alignment" << endl;
            return 1;
        }
        level = argv[3];
        if (level != "note" && level != "structure" && level != "shared_segments")
        {
            cerr << "Error: level must be 'note', 'structure', or 'shared_segments'" << endl;
            return 1;
        }
    }

    string db_path = "../database/folkroot.db";
    sqlite3 *db = initialize_database(db_path);
    if (!db)
    {
        return 1;
    }

    if (!is_segment && level == "shared_segments")
    {
        // Handle shared_segments level with the imported functionality
        cout << "Processing score alignments using shared segments approach..." << endl;
        process_shared_segments_alignments(db, level);
    }
    else
    {
        // Use the original approach for segment alignments or other score levels
        vector<FeatureData> data = get_feature_data(db, is_segment, level == "structure");
        process_alignments(db, data, is_segment, level);
    }

    sqlite3_exec(db, "COMMIT", nullptr, nullptr, nullptr);
    sqlite3_exec(db, "PRAGMA synchronous=FULL", nullptr, nullptr, nullptr);

    sqlite3_close(db);
    return 0;
}