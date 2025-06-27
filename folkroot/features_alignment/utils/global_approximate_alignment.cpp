/***
BSD 2-Clause License

Copyright (c) 2024, Hilda Romero-Velo
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
// Created by Hilda Romero-Velo on December 2024.
//

#include <string>
#include <iostream>
#include <algorithm>
#include <vector>
#include <fstream>
#include <numeric>
#include <sstream>
#include <optional>

using namespace std;

/**
 * @brief Function to compute the minimum of three integers.
 *
 * @param a First integer to compare.
 * @param b Second integer to compare.
 * @param c Third integer to compare.
 *
 * @return int The minimum value between the three integers.
 */
int min_of_three(int a, int b, int c)
{
    return min(min(a, b), c);
}

/**
 * @brief Computes the global alignment distance between two score features.
 *
 * This function calculates the global alignment distance between two score features
 * using dynamic programming. The algorithm uses a scoring scheme based on matching and mismatching
 * characters to determine the best alignment position. The function returns the distance between
 * the two provided score features.
 *
 * @param score_1_feature The first score feature to be compared.
 * @param score_2_feature The second score feature to be compared.
 * @param match_score Score value for matching characters in the alignment
 * @param mismatch_penalty Penalty value for mismatching characters in the alignment
 * @param gap_penalty Gap penalty value for the alignment computation
 *
 * @return int The global alignment distance between the two score features.
 */
int global_alignment(const vector<optional<int>> &score_1_feature,
                     const vector<optional<int>> &score_2_feature,
                     const int match_score, const int mismatch_penalty,
                     const int gap_penalty)
{
    size_t f1_size = score_1_feature.size();
    size_t f2_size = score_2_feature.size();

    vector<int> prev_column(f2_size + 1);
    vector<int> current_column(f2_size + 1);

    // Initialize first row
    for (int i = 0; i <= f2_size; ++i)
    {
        prev_column[i] = i * gap_penalty;
    }
    current_column = prev_column;

    // Compute distance matrix
    for (int i = 1; i <= f1_size; ++i)
    {
        current_column[0] = i * gap_penalty;
        for (int j = 1; j <= f2_size; ++j)
        {
            int score = mismatch_penalty;

            // Case 1: Both cells are null - consider it a match
            if (!score_1_feature[i - 1].has_value() &&
                !score_2_feature[j - 1].has_value())
            {
                score = match_score;
            }
            // Case 2: Both cells have values - check if they match
            else if (score_1_feature[i - 1].has_value() &&
                     score_2_feature[j - 1].has_value())
            {
                if (score_1_feature[i - 1].value() == score_2_feature[j - 1].value())
                {
                    score = match_score;
                }
            }
            // Case 3: One cell is null and the other isn't - treat as mismatch
            else
            {
                score = mismatch_penalty;
            }

            current_column[j] = min_of_three(
                prev_column[j - 1] + score,
                prev_column[j] + gap_penalty,
                current_column[j - 1] + gap_penalty);
        }
        prev_column = current_column;
    }

    return current_column[f2_size];
}