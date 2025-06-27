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
 # This script extracts a segment of a **kern file given a start and end note.
 '

#!/bin/bash

# Directory where the current script is located
script_dir=$(dirname "$(realpath "$0")")

input_file=""
start_note=""
end_note=""
output_file=""

usage() {
    echo "Usage: $0 -i <input_file> -s <start_note> -e <end_note> -o <output_file>"
    exit 1
}

# Parse command-line arguments
while getopts "i:s:e:o:" opt; do
    case "$opt" in
    i) input_file="$OPTARG" ;;
    s) start_note="$OPTARG" ;;
    e) end_note="$OPTARG" ;;
    o) output_file="$OPTARG" ;;
    *) usage ;;
    esac
done

# Check if all required arguments are provided
if [[ -z "$input_file" || -z "$start_note" || -z "$end_note" || -z "$output_file" ]]; then
    usage
fi

output_dir=$(dirname "$output_file")
mkdir -p "$output_dir"

log_dir="$script_dir/../logs"
log_file="$log_dir/segment_extraction_error.log"

# Extract the segment of the **kern file based on the start and end notes
sed '/\*-\s*$/d' "$input_file" | awk -v start="$start_note" -v end="$end_note" -v log_dir="$log_dir" -v log_file="$log_file" 'BEGIN { 
        note_count = -1;  # Start counting from 0
        header = 1;
        extracting = 1;
        found_notes = 0;
    } 
    /^!!/ { print; next }  # Keep header comments
    /^\*\*/ { print; header = 0; next }  # Keep interpretations
    /^\*/ { if (!header && extracting) print; next }  # Keep interpretation changes
    /^[^!*]/ && extracting { 
        split($0, notes, /\s+/); 
        new_line = "";
        for (i in notes) {
            if (notes[i] ~ /[a-gA-G]/) {
                note_count++;
            }
            if (note_count >= start && note_count <= end) {
                new_line = new_line notes[i] " ";
                found_notes = 1;
            }
        }
        if (new_line != "") {
            print new_line;
        }
        if (note_count > end) {
            extracting = 0;
        }
    }
    END {
        if (found_notes) {
            print "*-"  # Always add *- for spine closure at the end
        } else {
            system("mkdir -p " log_dir)  # Create log directory only when needed
            print "WARNING: No notes were extracted for range " start "-" end " in " FILENAME >> log_file
        }
    }' >"$output_file"
