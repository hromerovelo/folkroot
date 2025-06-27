"""
BSD 2-Clause License

Copyright (c) 2023, Hilda Romero-Velo
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
  Created by Hilda Romero-Velo on July 2023.
"""

""" 
  This script compiles **kern feature analyses (chromatic, diatonic, rhythmic) into JSON files
  for each segment or score, discarding unnecessary data and separating values with semicolons (;). 
"""

import os
import json
import shutil
from fractions import Fraction
import argparse

# Parse command-line arguments
parser = argparse.ArgumentParser(
    description="Process features from scores or segments."
)
parser.add_argument("--segment", action="store_true", help="Process as segment")
args = parser.parse_args()

script_dir = os.path.dirname(os.path.abspath(__file__))
data_dir = os.path.abspath(os.path.join(script_dir, "../../data"))

# Directories containing **kern feature analysis
if args.segment:
    computed_dir = os.path.join(data_dir, "computed", "segments", "features")
else:
    computed_dir = os.path.join(data_dir, "computed", "scores", "features")

chromatic_dir = os.path.join(computed_dir, "corpus_analysis", "chromatic_analysis")
diatonic_dir = os.path.join(computed_dir, "corpus_analysis", "diatonic_analysis")
rhythmic_dir = os.path.join(computed_dir, "corpus_analysis", "rhythmic_analysis")

# File suffixes for each analyzed segment feature
chromatic_end = "_chromatic.txt"
diatonic_end = "_diatonic.txt"
rhythmic_end = "_rhythmic.txt"

# Target directory
jsons_dir = os.path.join(computed_dir, "corpus_jsons")
try:
    os.makedirs(jsons_dir)
except FileExistsError:
    shutil.rmtree(jsons_dir)
except Exception as e:
    print(f"An error occurred while creating directory '{jsons_dir}': {e}")


def save_json_file(filename, data):
    with open(os.path.join(jsons_dir, filename + ".json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


def extract_feature(filepath):
    """
    Extracts and cleans feature values from a **kern format file by removing "+" signs,
    converting values to integers, and omitting those that match a specified ignore_value
    (representing no change in frequency).

    Args:
        filepath (str): Path to a file containing feature analysis in **kern format.

    Returns:
        str: A string of cleaned feature values, separated by semicolons.

    Notes:
        Lines that cannot be converted to integers are skipped.
    """
    feature = ""
    with open(filepath, "r", encoding="utf8") as f:
        for line in f:
            try:
                # Split the line using strip and keep the first part
                part = line.split()[0]
                step = int(part.strip().replace("+", ""))
                feature += f"{step};"
            except ValueError:
                continue
    return feature


# Processing chromatic feature. + sign is removed.
def extract_chromatic(filepath):
    return extract_feature(filepath)


# Processing diatonic feature. + sign is removed.
def extract_diatonic(filepath):
    return extract_feature(filepath)


# Processing rhythmic feature. Ties values are joined, rests are mantained and rhythm
# ratio is computed.
def extract_rhythm(filepath):
    rhythm_feature = ""
    old_r = None  # Tracks initial note duration for ratio computation
    sum_r = 0  # Tracks cumulative duration of tied notes
    num_of_ties = 0  # Tracks number of ties in a sequence

    with open(filepath, "r", encoding="utf8") as f:
        for line in f:
            larray = line.split()
            try:
                # Check if first element contains only a dot (ignoring spaces)
                if larray[0].strip() == ".":
                    # Extract the number from the second element
                    duration_str = "".join(filter(str.isdigit, larray[1]))
                    if not duration_str:
                        continue

                    duration = int(duration_str)
                    # Check if there's a dot after the number
                    if "." in larray[1]:
                        r1 = Fraction(3, duration * 2)
                    else:
                        r1 = Fraction(1, duration)
                else:
                    if larray[0].strip() == "0":
                        continue
                    else:
                        r1 = Fraction(larray[0])

                if r1 != 0:
                    # Initialize first note duration as baseline
                    if old_r == None:
                        old_r = r1 if "r" not in larray[1] else None
                    else:
                        # Accumulate duration for tied notes
                        if "[" in larray[1].strip():
                            sum_r += r1
                            num_of_ties += 1
                        elif "]" in larray[1].strip():
                            sum_r += r1
                            rhythm_feature += (
                                str(sum_r / old_r) + "T" + str(num_of_ties) + ";"
                            )
                            old_r = sum_r  # Update baseline to tied notes duration
                            sum_r = 0
                            num_of_ties = 0
                        elif sum_r != 0:
                            sum_r += r1
                            num_of_ties += 1
                        else:
                            # Identify rests and compute rhythm ratio
                            rest = "r" if "r" in larray[1] else ""
                            rhythm_feature += str(r1 / old_r) + rest + ";"
                            old_r = r1  # Update baseline to new note duration
            except (ValueError, IndexError):
                continue

    return rhythm_feature


if __name__ == "__main__":
    with os.scandir(chromatic_dir) as files:
        for f in files:
            segment = {}
            id = f.name.removesuffix(chromatic_end)
            segment["id"] = id
            # Extract chromatic, diatonic, and rhythmic features for each segment
            segment["chromatic"] = extract_chromatic(f.path)
            segment["diatonic"] = extract_diatonic(
                os.path.join(diatonic_dir, id + diatonic_end)
            )
            segment["rhythm"] = extract_rhythm(
                os.path.join(rhythmic_dir, id + rhythmic_end)
            )
            save_json_file(id, segment)
