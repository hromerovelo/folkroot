"""
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
"""

"""
  Created by Hilda Romero-Velo on March 2025.
"""

"""
  Script to transfer cluster data from Excel files to the database.
  
  This script reads cluster assignments from the Excel files produced by the
  qt_segments_clustering.py script and populates the SegmentGroup and 
  SegmentToGroup tables in the database.
  
  Usage:
    python transfer_clusters_to_db.py -f <feature>
    python transfer_clusters_to_db.py -f all    # Process all features
"""

import argparse
import os
import sqlite3
import sys
import pandas as pd


def get_all_valid_features():
    """
    Get a list of all valid feature types (excluding 'all').

    Returns:
        list: List of valid feature types
    """
    return [
        "diatonic",
        "chromatic",
        "rhythmic",
        "diatonic_rhythmic",
        "chromatic_rhythmic",
    ]


def validate_feature(feature):
    """
    Validate that the feature is one of the allowed values.

    Args:
        feature (str): The feature to validate

    Returns:
        bool: True if the feature is valid
    """
    valid_features = get_all_valid_features() + ["all"]

    if feature not in valid_features:
        print(
            f"Error: '{feature}' is not a valid feature. Valid features are: {', '.join(valid_features)}"
        )
        return False
    return True


def get_excel_path(script_dir, feature):
    """
    Generate the path to the Excel file based on the feature.

    Args:
        script_dir (str): The directory of the current script
        feature (str): The feature type

    Returns:
        str: The full path to the Excel file
    """
    excel_path = os.path.join(
        script_dir,
        "results",
        f"{feature}_clustering",
        f"segments_clustering_{feature}.xlsx",
    )

    if not os.path.exists(excel_path):
        print(f"Error: Excel file not found at {excel_path}")
        print("Make sure to run qt_segments_clustering.py with the same feature first.")
        return None

    return excel_path


def read_cluster_data(excel_path):
    """
    Read the cluster data from the Excel file.

    Args:
        excel_path (str): Path to the Excel file

    Returns:
        pandas.DataFrame or None: DataFrame with segment_id and cluster_id columns
    """
    try:
        df = pd.read_excel(excel_path)

        # Verify required columns exist
        required_columns = ["segment_id", "cluster_id"]
        missing_columns = [col for col in required_columns if col not in df.columns]

        if missing_columns:
            print(
                f"Error: The Excel file is missing required columns: {', '.join(missing_columns)}"
            )
            return None

        # Select only the required columns
        cluster_data = df[["segment_id", "cluster_id"]].copy()

        # Ensure data types
        cluster_data["segment_id"] = cluster_data["segment_id"].astype(int)
        cluster_data["cluster_id"] = cluster_data["cluster_id"].astype(int)

        print(f"Found {len(cluster_data)} segment-cluster assignments")
        print(f"Number of unique clusters: {cluster_data['cluster_id'].nunique()}")

        return cluster_data

    except Exception as e:
        print(f"Error reading Excel file: {str(e)}")
        return None


def update_database(cursor, cluster_data, feature):
    """
    Update the database with the cluster data.

    Args:
        cursor: SQLite cursor for database operations
        cluster_data (pandas.DataFrame): DataFrame with segment_id and cluster_id columns
        feature (str): The feature type

    Returns:
        bool: True if the update was successful
    """
    try:
        # Get unique cluster IDs
        unique_clusters = cluster_data["cluster_id"].unique()

        # Begin transaction
        cursor.execute("BEGIN TRANSACTION")

        # Insert into SegmentGroup table (if not exists)
        for cluster_id in unique_clusters:
            cursor.execute(
                """
                INSERT OR IGNORE INTO SegmentGroup (group_id)
                VALUES (?)
                """,
                (int(cluster_id),),
            )

        # Clear any existing mappings for this feature type
        cursor.execute(
            """
            DELETE FROM SegmentToGroup
            WHERE feature_type = ?
            """,
            (feature,),
        )

        # Insert into SegmentToGroup table
        segment_to_group_data = [
            (int(row["segment_id"]), int(row["cluster_id"]), feature)
            for _, row in cluster_data.iterrows()
        ]

        cursor.executemany(
            """
            INSERT OR REPLACE INTO SegmentToGroup (segment_id, group_id, feature_type)
            VALUES (?, ?, ?)
            """,
            segment_to_group_data,
        )

        # Commit transaction
        cursor.execute("COMMIT")

        print(
            f"Successfully inserted {len(segment_to_group_data)} segment-to-group mappings"
        )
        print(f"Successfully inserted {len(unique_clusters)} unique segment groups")

        return True

    except Exception as e:
        # Rollback in case of error
        cursor.execute("ROLLBACK")
        print(f"Error updating database: {str(e)}")
        return False


def verify_database_update(cursor, cluster_data, feature):
    """
    Verify that the database was updated correctly.

    Args:
        cursor: SQLite cursor for database operations
        cluster_data (pandas.DataFrame): DataFrame with segment_id and cluster_id columns
        feature (str): The feature type

    Returns:
        bool: True if the verification was successful
    """
    try:
        # Count groups in SegmentGroup
        cursor.execute("SELECT COUNT(*) FROM SegmentGroup")
        total_groups = cursor.fetchone()[0]

        # Count mappings for this feature in SegmentToGroup
        cursor.execute(
            """
            SELECT COUNT(*) FROM SegmentToGroup
            WHERE feature_type = ?
            """,
            (feature,),
        )
        total_mappings = cursor.fetchone()[0]

        # Verify counts match expected numbers
        expected_mappings = len(cluster_data)
        if total_mappings != expected_mappings:
            print(
                f"Warning: Expected {expected_mappings} mappings but found {total_mappings}"
            )
            return False

        print("\nVerification successful:")
        print(f"- Total groups in database: {total_groups}")
        print(f"- Total mappings for feature '{feature}': {total_mappings}")

        return True

    except Exception as e:
        print(f"Error during verification: {str(e)}")
        return False


def process_feature(feature, script_dir, db_path):
    """
    Process a single feature - read Excel data and update database.

    Args:
        feature (str): The feature to process
        script_dir (str): Directory of the current script
        db_path (str): Path to the database

    Returns:
        bool: True if processing was successful
    """
    print(f"\nProcessing feature '{feature}'...")
    excel_path = get_excel_path(script_dir, feature)
    if not excel_path:
        return False

    cluster_data = read_cluster_data(excel_path)
    if cluster_data is None:
        return False

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        print(f"Updating database with cluster data for feature '{feature}'...")
        success = update_database(cursor, cluster_data, feature)

        if success:
            verify_database_update(cursor, cluster_data, feature)
            print(
                f"\nDatabase update for feature '{feature}' completed successfully.\n"
            )
        else:
            print(f"ERROR: Database update for feature '{feature}' failed.")

        conn.close()
        return success

    except sqlite3.Error as e:
        print(f"SQLite error: {str(e)}")
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Transfer cluster data to database")
    parser.add_argument(
        "-f",
        "--feature",
        type=str,
        required=True,
        help="Feature type (e.g., diatonic, chromatic, rhythmic, diatonic_rhythmic, chromatic_rhythmic, all)",
    )

    args = parser.parse_args()

    if not validate_feature(args.feature):
        sys.exit(1)

    script_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.abspath(os.path.join(script_dir, "../database/folkroot.db"))

    if not os.path.exists(db_path):
        print(f"Error: Database not found at {db_path}")
        sys.exit(1)

    # Process features
    if args.feature == "all":
        print(f"Processing all features...\n")
        all_features = get_all_valid_features()
        success_count = 0

        for feature in all_features:
            success = process_feature(feature, script_dir, db_path)
            if success:
                success_count += 1

        print("\n" + "=" * 50)
        print(f"Completed processing {success_count}/{len(all_features)} features")

        if success_count < len(all_features):
            print("Some features failed to process. Check the logs above for details.")
            sys.exit(1)
    else:
        # Process single feature
        success = process_feature(args.feature, script_dir, db_path)
        if not success:
            sys.exit(1)
