"""
BSD 2-Clause License

Copyright (c) 2025, Hilda Romero-Velo
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

* Redistributions of source code must retain the above copyright notice, this
  list of conditions and the following disclaimer.

* Redistributions in binary form must reproduce the above copyright notice, this
  list of conditions and the following disclaimer in the documentation
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
"""

"""
  Created by Hilda Romero-Velo on March 2025.
"""

"""
  This script processes JSON files containing feature values for scores or segments. It removes
  extra notation and unisons for each individual feature and it also combines melodic and rhythmic
  feature values into a single string. The processed values are saved to the database.
    
  Input: JSON files with feature values for each score.
"""

import os
import json
import sqlite3
import logging
import argparse


# Parse command-line arguments
parser = argparse.ArgumentParser(description="")
parser.add_argument("--segment", action="store_true", help="Process as segment")
args = parser.parse_args()

# Calculate base directories
script_dir = os.path.dirname(os.path.abspath(__file__))
data_dir = os.path.abspath(os.path.join(script_dir, "../../data"))


# Define source directory for JSON files with feature values
if args.segment:
    jsons_dir = os.path.join(
        data_dir, "computed", "segments", "features", "corpus_jsons"
    )
else:
    jsons_dir = os.path.join(data_dir, "computed", "scores", "features", "corpus_jsons")

# Define database file and error log file
db_file = os.path.join(script_dir, "../../database/folkroot.db")
error_log = os.path.join(script_dir, "../../database/folkroot_db_error_log.txt")

# Configure logging
logging.basicConfig(
    filename=error_log,
    level=logging.ERROR,
    format="%(asctime)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def remove_extra_notation(data, ignore_value):
    """
    Removes extra notation and unisons from feature values.

    Args:
        data (str): Semicolon-separated original feature values.
        ignore_value (str): Value to ignore in the translation representing unison.

    Returns:
        str: Feature values without extra notation and unisons.
    """
    values = data.split(";")
    values.pop()  # Remove the last empty element
    result = ""
    for v in values:
        if v != ignore_value:
            if "T" in v:
                v = v.split("T")[0]
            result += v.replace("r", "")
            result += ";"
    return result


def combine_melodic_and_rhythmic_feature(
    filename,
    melodic_feature,
    rhythmic_feature,
    unison_value,
):
    """
    Combines melodic and rhythmic feature values taking ties and rests into account. Values are
    separated by semicolons. Melodic feature relies on the uneven indexes and rhythmic feature on
    the even indexes. Rests are represented by the character 'r' in the melodic feature.

    Args:
        filename (str): Name of the file being processed.
        melodic_feature (str): Semicolon-separated melodic feature values.
        rhythmic_feature (str): Semicolon-separated rhythmic feature values.
        unison_value (str): Value representing unison in the melodic feature.

    Returns:
        str: Combined feature values separated by semicolons.
    """
    melodic_values = melodic_feature.split(";")
    melodic_values.pop()  # Remove the last empty element
    rhythmic_values = rhythmic_feature.split(";")
    rhythmic_values.pop()  # Remove the last empty element
    result = ""
    rest_char = "r"  # Melodic value for rests

    melodic_index = 0

    for rhythmic_value in rhythmic_values:
        result += (
            melodic_values[melodic_index]
            if melodic_index < len(melodic_values)
            else rest_char
        )
        result += ";"

        # Identify ties to skip unison values in the melodic feature
        if "T" in rhythmic_value:
            rhythmic_value, skip_count = rhythmic_value.split("T")
            skip_count = int(skip_count)
        else:
            skip_count = 0

        # Identify rests and remove the last added melodic value
        if "r" in rhythmic_value:
            result = result[:-2]  # Remove the last added melodic value and semi-colon
            if result and result[-1] == "-":  # Case melodic value is negative
                result = result[:-1]
            result += rest_char + ";"
            melodic_index -= 1
            rhythmic_value = rhythmic_value.replace("r", "")

        result += rhythmic_value + ";"

        if skip_count > 0:
            for _ in range(skip_count):
                melodic_index += 1
                if (
                    melodic_index < len(melodic_values)
                    and melodic_values[melodic_index] != unison_value
                ):
                    logging.error(
                        f"{filename}: Expected '{unison_value}' but found '{melodic_values[melodic_index]}' at index {melodic_index}. Current result: {result}"
                    )
                    return result  # Stop processing and return the current result

        melodic_index += 1

    if melodic_index < len(melodic_values):
        logging.error(
            f"{filename}: Melodic and rhythmic sequences have different lengths. Current result: {result}. Melodic index: {melodic_index}. Melodic values: {melodic_values}. Rhythmic values: {rhythmic_values}"
        )
        return result  # Stop processing and return the current result

    # Check if the length of result is even
    if len(result.split(";")[:-1]) % 2 != 0:
        logging.error(
            f"Segment {filename}: The length of the combined feature sequence is not even. Current result: {result}. Length: {len(result)}."
        )
        return result  # Stop processing and return the current result

    return result


def check_database_and_tables():
    """
    Checks if the database file and required tables exist.

    Raises:
        SystemExit: If the database file or required tables do not exist.
    """
    if not os.path.isfile(db_file):
        raise SystemExit(f"ERROR: Database file '{db_file}' does not exist.")
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    # Check if the required tables exist in the database
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='Score';"
    )
    score_table_exists = cursor.fetchone()
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='Segment';"
    )
    segment_table_exists = cursor.fetchone()

    if not score_table_exists or not segment_table_exists:
        conn.close()
        raise SystemExit(
            f"ERROR: Tables 'Score' or 'Segment' do not exist in {db_file}."
        )

    conn.close()


def save_data_to_db(
    identifier,
    chromatic,
    diatonic,
    rhythm,
    chromatic_rhythmic,
    diatonic_rhythmic,
    is_segment,
):
    """
    Save features for a segment or score to the database.

    Args:
        identifier (str): The ID of the segment or the filename of the score.
        chromatic (str): The chromatic feature values.
        diatonic (str): The diatonic feature values.
        rhythm (str): The rhythm feature values.
        chromatic_rhythmic (str): The combined chromatic and rhythmic feature values.
        diatonic_rhythmic (str): The combined diatonic and rhythmic feature values.
        is_segment (bool): Flag indicating if the data is for segments.
    """
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    table_name = "Segment" if is_segment else "Score"
    id_column = "segment_id" if is_segment else "filename"

    try:
        cursor.execute(
            f"""
            UPDATE {table_name}
            SET chromatic_feature = ?, diatonic_feature = ?, rhythmic_feature = ?, 
            chromatic_rhythmic_feature = ?, diatonic_rhythmic_feature = ?
            WHERE {id_column} = ?
            """,
            (
                chromatic,
                diatonic,
                rhythm,
                chromatic_rhythmic,
                diatonic_rhythmic,
                identifier,
            ),
        )
        conn.commit()
    except sqlite3.Error as e:
        print(f"Database error: {e}")

    conn.close()


def iterate_jsons_directory(is_segment):
    """
    Iterates over the JSON files in the directory and processes the feature values.
    It saves the processed values to the database.

    Args:
        is_segment (bool): Flag indicating if the data is for segments.
    """
    with os.scandir(jsons_dir) as files:
        for file in files:
            with open(file.path) as f:
                try:
                    data = json.load(f)

                    # Translate each feature into single-character notation
                    chromatic = remove_extra_notation(data["chromatic"], "0")
                    diatonic = remove_extra_notation(data["diatonic"], "1")
                    rhythm = remove_extra_notation(data["rhythm"], None)

                    chromatic_rhythmic = combine_melodic_and_rhythmic_feature(
                        data["id"],
                        data["chromatic"],
                        data["rhythm"],
                        "0",
                    )

                    diatonic_rhythmic = combine_melodic_and_rhythmic_feature(
                        data["id"],
                        data["diatonic"],
                        data["rhythm"],
                        "1",
                    )

                    identifier = (
                        data["id"] + ".krn"
                        if not is_segment
                        else os.path.splitext(data["id"])[0].split("_")[-1]
                    )
                    save_data_to_db(
                        identifier,
                        chromatic,
                        diatonic,
                        rhythm,
                        chromatic_rhythmic,
                        diatonic_rhythmic,
                        is_segment,
                    )

                except json.JSONDecodeError as e:
                    print(f"Error reading JSON from file {file.path}: {e}")


if __name__ == "__main__":
    check_database_and_tables()

    # Set features for all scores or segments
    iterate_jsons_directory(args.segment)
