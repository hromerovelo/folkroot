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
  This script extracts segments from **kern files based on the indices provided in an Excel file
  and saves them as individual **kern files in a specified directory.
"""

import pandas as pd
import subprocess
import sqlite3
import os

script_dir = os.path.dirname(os.path.abspath(__file__))
data_dir = os.path.abspath(os.path.join(script_dir, "../../data"))
origin_dir = os.path.abspath(os.path.join(data_dir, "origin"))


def validate_segments(segments):
    """Validate that segments are in ascending order."""
    prev = -1
    for seg in segments:
        if seg <= prev:
            return False
        prev = seg
    return True


def process_segment_index(segment_str):
    """Process segment index string and return list of integers."""
    clean_str = segment_str.replace("[", "").replace("]", "")
    return [int(x.strip()) for x in clean_str.split(",")]


def log_error(error_log_path, file_id, filename, error_msg):
    """Log error to file, creating directory if needed."""
    log_dir = os.path.dirname(error_log_path)
    os.makedirs(log_dir, exist_ok=True)

    if not os.path.exists(error_log_path):
        with open(error_log_path, "w") as error_log:
            error_log.write("ID\tFilename\tError\n")

    with open(error_log_path, "a") as error_log:
        error_log.write(f"{file_id}\t{filename}\t{error_msg}\n")


def insert_score(cursor, score_id, filename, dataset, genre):
    """Insert a score into the database if it does not exist."""
    cursor.execute(
        "INSERT OR IGNORE INTO Score (score_id, filename, dataset, genre) VALUES (?, ?, ?, ?)",
        (score_id, filename, dataset, genre),
    )


def insert_segment(cursor, score_id, start_note, end_note):
    """Insert a segment into the database and return its ID."""
    cursor.execute(
        """INSERT INTO Segment (score_id, start_note, end_note) VALUES (?, ?, ?)""",
        (score_id, start_note, end_note),
    )
    return cursor.lastrowid


if __name__ == "__main__":
    # Read Excel file
    excel_path = os.path.abspath(
        os.path.join(origin_dir, "gal_irl_dataset_segments.xlsx")
    )
    df = pd.read_excel(excel_path)

    output_dir = os.path.abspath(os.path.join(data_dir, "segments"))
    os.makedirs(output_dir, exist_ok=True)

    error_log_path = os.path.abspath(
        os.path.join(script_dir, "logs", "score_segments_errors.log")
    )

    # Get the absolute path of the extract_kern_segment.sh script
    script_path = os.path.abspath(os.path.join(script_dir, "extract_kern_segment.sh"))

    # Connect to database
    db_path = os.path.abspath(os.path.join(script_dir, "../../database/folkroot.db"))
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    for _, row in df.iterrows():
        filename = row["filename"]
        segment_index = row["segment_index"]
        file_id = row["id"]
        dataset = row["dataset"]
        genre = row["genre"]

        try:
            # Insert score into database
            insert_score(cursor, file_id, filename, dataset, genre)

            # Process segment indices
            segments = process_segment_index(str(segment_index))

            if not validate_segments(segments):
                log_error(
                    error_log_path,
                    file_id,
                    filename,
                    f"Segments not in ascending order: {segment_index}",
                )
                continue

            # Create segments
            prev_end = -1
            for i in range(len(segments)):
                start_note = prev_end + 1
                end_note = segments[i]

                # Insert segment into database
                segment_id = insert_segment(cursor, file_id, start_note, end_note)

                # Construct input and output file paths
                input_file = os.path.abspath(
                    os.path.join(origin_dir, "kern_gal_irl_dataset", filename)
                )

                output_file = os.path.abspath(
                    os.path.join(
                        output_dir,
                        f"{os.path.splitext(filename)[0]}_{start_note}_{end_note}_{segment_id}.krn",
                    )
                )

                # Execute the bash script
                cmd = [
                    "bash",
                    script_path,
                    "-i",
                    input_file,
                    "-s",
                    str(start_note),
                    "-e",
                    str(end_note),
                    "-o",
                    output_file,
                ]

                subprocess.run(cmd, check=True)
                prev_end = end_note

            conn.commit()

        except Exception as e:
            log_error(
                error_log_path, file_id, filename, f"Error processing file: {str(e)}"
            )
            conn.rollback()

    conn.close()
