"""Behavioral checks for public visibility. Run with uv run -m unittest discover -s scripts."""

import json
import sqlite3
import struct
import tempfile
import unittest
from pathlib import Path

from export_trees import export_trees, signed_tree_rows


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.package = Path(self.directory.name) / "trees.gpkg"
        self.output = Path(self.directory.name) / "trees.geojson"
        self.connection = sqlite3.connect(self.package)
        self.addCleanup(self.connection.close)
        self.connection.executescript("""
            CREATE TABLE tree_locations (tree_uuid TEXT, tree_id INTEGER, point_id INTEGER, geom BLOB);
            CREATE TABLE observations (fid INTEGER PRIMARY KEY, tree_uuid TEXT, dateobserved TEXT, status TEXT, sign_presence TEXT);
            CREATE TABLE species_master_current (tree_id INTEGER, common_name TEXT, scientific_name TEXT, family TEXT, origin TEXT);
        """)

    def point(self, uuid, tree_id, point_id):
        geometry = (
            b"GP\x00\x01"
            + struct.pack("<I", 4326)
            + struct.pack("<BIdd", 1, 1, -120.74, 35.33)
        )
        self.connection.execute(
            "INSERT INTO tree_locations VALUES (?, ?, ?, ?)",
            (uuid, tree_id, point_id, geometry),
        )

    def observation(self, fid, uuid, date, status, presence):
        self.connection.execute(
            "INSERT INTO observations VALUES (?, ?, ?, ?, ?)",
            (fid, uuid, date, status, presence),
        )
        self.connection.commit()

    def test_presence_alone_controls_visibility(self):
        for i, (status, presence) in enumerate(
            [
                ("OK", "Present"),
                ("Needs Attention", "Present"),
                ("New Species", "Present"),
                ("OK", "Absent"),
                ("Needs Attention", "Unknown"),
                ("OK", None),
            ],
            1,
        ):
            self.point(str(i), i, i)
            self.observation(i, str(i), "2026-08-09T20:00:00Z", status, presence)
        self.point("unobserved", 7, 7)
        self.connection.commit()
        self.assertEqual(
            [r["tree_id"] for r in signed_tree_rows(self.package)], [1, 2, 3]
        )

    def test_latest_observation_wins_including_unknown_and_timestamp_ties(self):
        for i in range(1, 5):
            self.point(str(i), i, i)
            self.observation(i, str(i), "2026-08-08T20:00:00Z", "OK", "Present")
        self.observation(10, "1", "2026-08-09T20:00:00Z", "Needs Attention", "Absent")
        self.observation(11, "2", "2026-08-09T20:00:00Z", "OK", "Unknown")
        self.observation(12, "3", "2026-08-08T20:00:00Z", "OK", "Absent")
        self.observation(13, "4", None, "OK", "Absent")
        self.assertEqual([r["tree_id"] for r in signed_tree_rows(self.package)], [4])

    def test_same_species_locations_stay_independent(self):
        self.point("signed", 84, 102)
        self.point("unsigned", 84, 47)
        self.observation(1, "signed", "2026-08-08", "Needs Attention", "Present")
        self.observation(2, "unsigned", "2026-08-09", "Needs Attention", "Absent")
        self.assertEqual(len(signed_tree_rows(self.package)), 1)

    def test_export_preserves_photos_and_keeps_working_fields_private(self):
        self.point("signed", 84, 102)
        self.observation(1, "signed", "2026-08-08", "Needs Attention", "Present")
        self.output.write_text(
            json.dumps(
                {
                    "features": [
                        {
                            "properties": {
                                "tree_id": 84,
                                "photo_url": "https://example.com/tree.jpg",
                            }
                        }
                    ]
                }
            )
        )
        self.assertEqual(export_trees(self.package, self.output, False), 1)
        feature = json.loads(self.output.read_text())["features"][0]
        self.assertEqual(feature["geometry"]["coordinates"], [-120.74, 35.33])
        self.assertEqual(
            feature["properties"]["photo_url"], "https://example.com/tree.jpg"
        )
        self.assertEqual(
            set(feature["properties"]),
            {
                "tree_id",
                "common_name",
                "scientific_name",
                "family",
                "origin",
                "photo_url",
            },
        )


if __name__ == "__main__":
    unittest.main()
