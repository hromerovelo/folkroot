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

#include "common.hpp"
#include <iostream>

using namespace std;

sqlite3 *initialize_database(const string &db_path)
{
    sqlite3 *db;
    if (sqlite3_open(db_path.c_str(), &db) != SQLITE_OK)
    {
        cerr << "Cannot open database: " << sqlite3_errmsg(db) << endl;
        return nullptr;
    }

    // Essential settings - keep these even in Docker:
    sqlite3_exec(db, "PRAGMA journal_mode=WAL", nullptr, nullptr, nullptr);
    sqlite3_exec(db, "PRAGMA synchronous=OFF", nullptr, nullptr, nullptr);
    sqlite3_exec(db, "PRAGMA temp_store=MEMORY", nullptr, nullptr, nullptr);
    sqlite3_exec(db, "PRAGMA locking_mode=EXCLUSIVE", nullptr, nullptr, nullptr);

    // For Docker with limited resources (4-8GB RAM), comment these out or reduce values:
    sqlite3_exec(db, "PRAGMA cache_size=-2000000", nullptr, nullptr, nullptr);
    sqlite3_exec(db, "PRAGMA mmap_size=8589934592", nullptr, nullptr, nullptr);
    sqlite3_exec(db, "PRAGMA page_size=4096", nullptr, nullptr, nullptr);

    sqlite3_exec(db, "BEGIN TRANSACTION", nullptr, nullptr, nullptr);

    return db;
}

void save_alignments_batch(sqlite3 *db, const vector<AlignmentScores> &alignments, bool is_segment)
{
    const char *sql = is_segment ? "INSERT INTO SegmentAlignment (segment_id_1, segment_id_2, diatonic_score, "
                                   "chromatic_score, rhythmic_score, diatonic_rhythmic_score, chromatic_rhythmic_score) "
                                   "VALUES (?,?,?,?,?,?,?)"
                                 : "INSERT INTO ScoreAlignment (score_id_1, score_id_2, level, diatonic_score, "
                                   "chromatic_score, rhythmic_score, diatonic_rhythmic_score, chromatic_rhythmic_score) "
                                   "VALUES (?,?,?,?,?,?,?,?)";

    sqlite3_stmt *stmt;
    if (sqlite3_prepare_v2(db, sql, -1, &stmt, nullptr) != SQLITE_OK)
    {
        cerr << "Failed to prepare batch insert: " << sqlite3_errmsg(db) << endl;
        return;
    }

    for (const auto &a : alignments)
    {
        int idx = 1;
        sqlite3_bind_int(stmt, idx++, min(a.id1, a.id2));
        sqlite3_bind_int(stmt, idx++, max(a.id1, a.id2));
        if (!is_segment)
        {
            sqlite3_bind_text(stmt, idx++, a.level.c_str(), -1, SQLITE_STATIC);
        }
        sqlite3_bind_int(stmt, idx++, a.diatonic_score);
        sqlite3_bind_int(stmt, idx++, a.chromatic_score);
        sqlite3_bind_int(stmt, idx++, a.rhythmic_score);
        sqlite3_bind_int(stmt, idx++, a.diatonic_rhythmic_score);
        sqlite3_bind_int(stmt, idx++, a.chromatic_rhythmic_score);

        if (sqlite3_step(stmt) != SQLITE_DONE)
        {
            cerr << "Failed to insert batch alignment: " << sqlite3_errmsg(db) << endl;
        }
        sqlite3_reset(stmt);
    }

    sqlite3_finalize(stmt);
}

vector<int> get_all_score_ids(sqlite3 *db)
{
    vector<int> score_ids;
    const char *sql = "SELECT DISTINCT score_id FROM Score";

    sqlite3_stmt *stmt;
    if (sqlite3_prepare_v2(db, sql, -1, &stmt, nullptr) != SQLITE_OK)
    {
        cerr << "Failed to prepare statement for score IDs: " << sqlite3_errmsg(db) << endl;
        return score_ids;
    }

    while (sqlite3_step(stmt) == SQLITE_ROW)
    {
        score_ids.push_back(sqlite3_column_int(stmt, 0));
    }

    sqlite3_finalize(stmt);
    return score_ids;
}