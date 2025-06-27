/*
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
*/

-- -----------------------------------------------------------------------------
-- Script: Database Schema for storing different alignments between the Galician
-- and Irish datasets.
-- Author: Hilda Romero-Velo
-- Date: 2025-03-07
-- -----------------------------------------------------------------------------

-- Enable foreign key constraints
PRAGMA foreign_keys = ON;

-- Drop tables if they exist to avoid conflicts
DROP TABLE IF EXISTS ScoreAlignment;
DROP TABLE IF EXISTS SegmentAlignment;
DROP TABLE IF EXISTS SegmentToGroup;
DROP TABLE IF EXISTS Segment;
DROP TABLE IF EXISTS SegmentGroup;
DROP TABLE IF EXISTS Score;

-- Table: Score
CREATE TABLE Score (
    score_id INTEGER PRIMARY KEY,
    filename TEXT NOT NULL,
    dataset TEXT NOT NULL CHECK (dataset IN ('galician', 'irish')),
    genre TEXT NOT NULL,
    diatonic_feature TEXT,
    chromatic_feature TEXT,
    rhythmic_feature TEXT,
    diatonic_rhythmic_feature TEXT,
    chromatic_rhythmic_feature TEXT
);

-- Table: ScoreAlignment
CREATE TABLE ScoreAlignment (
    score_alignment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    score_id_1 INTEGER NOT NULL,
    score_id_2 INTEGER NOT NULL,
    level TEXT NOT NULL CHECK (level IN ('note', 'structure', 'shared_segments')),
    diatonic_score INTEGER,
    chromatic_score INTEGER,
    rhythmic_score INTEGER, 
    diatonic_rhythmic_score INTEGER,
    chromatic_rhythmic_score INTEGER,
    FOREIGN KEY (score_id_1) REFERENCES Score(score_id) ON DELETE CASCADE,
    FOREIGN KEY (score_id_2) REFERENCES Score(score_id) ON DELETE CASCADE,
    UNIQUE (score_id_1, score_id_2, level)
);

-- Table: Segment
CREATE TABLE Segment (
    segment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    score_id INTEGER NOT NULL,
    start_note INTEGER NOT NULL,
    end_note INTEGER NOT NULL,
    diatonic_feature TEXT,
    chromatic_feature TEXT,
    rhythmic_feature TEXT,
    diatonic_rhythmic_feature TEXT,
    chromatic_rhythmic_feature TEXT,
    FOREIGN KEY (score_id) REFERENCES Score(score_id) ON DELETE CASCADE,
    UNIQUE (score_id, start_note) -- Natural Key
);

-- Table: SegmentAlignment
CREATE TABLE SegmentAlignment (
    segment_alignment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    segment_id_1 INTEGER NOT NULL,
    segment_id_2 INTEGER NOT NULL,
    diatonic_score INTEGER,
    chromatic_score INTEGER,
    rhythmic_score INTEGER,
    diatonic_rhythmic_score INTEGER,
    chromatic_rhythmic_score INTEGER,
    FOREIGN KEY (segment_id_1) REFERENCES Segment(segment_id) ON DELETE CASCADE,
    FOREIGN KEY (segment_id_2) REFERENCES Segment(segment_id) ON DELETE CASCADE,
    UNIQUE (segment_id_1, segment_id_2)
);

-- Table: SegmentGroup
CREATE TABLE SegmentGroup (
    group_id INTEGER PRIMARY KEY
);

-- Table: SegmentToGroup (Join table for Segment and SegmentGroup)
CREATE TABLE SegmentToGroup (
    segment_id INTEGER NOT NULL,
    group_id INTEGER NOT NULL,
    feature_type TEXT NOT NULL CHECK (
        feature_type IN ('chromatic', 'diatonic', 'rhythmic', 'chromatic_rhythmic', 'diatonic_rhythmic')
    ),
    PRIMARY KEY (segment_id, feature_type),
    FOREIGN KEY (segment_id) REFERENCES Segment(segment_id) ON DELETE CASCADE,
    FOREIGN KEY (group_id) REFERENCES SegmentGroup(group_id) ON DELETE CASCADE
);
