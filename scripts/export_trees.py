#!/usr/bin/env python3
"""
Export Trees to GeoJSON

Exports tree locations with species information from the geopackage
to a GeoJSON file for use in the web map.

Uses only Python standard library (no geopandas required).

Usage: python scripts/export_trees.py
"""

import sqlite3
import struct
import json
import os

# Configuration
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
GEOPACKAGE_PATH = os.path.join(PROJECT_ROOT, "cuesta-trees", "cuesta-trees.gpkg")
OUTPUT_GEOJSON = os.path.join(PROJECT_ROOT, "trees.geojson")


def parse_gpkg_point(blob):
    """
    Parse a GeoPackage binary geometry (point) to extract lon/lat.

    GeoPackage format:
    - Bytes 0-1: Magic number (GP)
    - Byte 2: Version
    - Byte 3: Flags (contains envelope indicator and byte order)
    - Bytes 4-7: SRS ID (int32)
    - Variable: Envelope (if present, based on flags)
    - Remainder: WKB geometry
    """
    if blob is None:
        return None, None

    # Check magic number
    if blob[0:2] != b'GP':
        return None, None

    flags = blob[3]
    byte_order = flags & 0x01  # 0 = big endian, 1 = little endian
    envelope_type = (flags >> 1) & 0x07

    # Calculate envelope size
    envelope_sizes = {0: 0, 1: 32, 2: 48, 3: 48, 4: 64}
    envelope_size = envelope_sizes.get(envelope_type, 0)

    # WKB starts after header (8 bytes) + envelope
    wkb_offset = 8 + envelope_size
    wkb = blob[wkb_offset:]

    # Parse WKB point
    # Byte 0: byte order (1 = little endian)
    # Bytes 1-4: geometry type (1 = Point)
    # Bytes 5-12: X (double)
    # Bytes 13-20: Y (double)
    wkb_byte_order = wkb[0]
    fmt = '<' if wkb_byte_order == 1 else '>'

    x, y = struct.unpack(f'{fmt}dd', wkb[5:21])
    return x, y  # lon, lat


def export_trees():
    """
    Load tree locations and species data, join them, and export as GeoJSON.
    """
    print(f"Loading data from '{GEOPACKAGE_PATH}'...")

    conn = sqlite3.connect(GEOPACKAGE_PATH)

    # Query tree locations with species info
    query = """
        SELECT
            t.tree_id,
            t.geom,
            s.common_name,
            s.scientific_name,
            s.family,
            s.origin
        FROM tree_locations t
        LEFT JOIN species_master_current s ON t.tree_id = s.tree_id
        ORDER BY t.tree_id
    """

    cursor = conn.execute(query)
    rows = cursor.fetchall()
    print(f"Loaded {len(rows)} tree locations.")

    # Build GeoJSON
    features = []
    missing_count = 0

    for row in rows:
        tree_id, geom_blob, common_name, scientific_name, family, origin = row

        lon, lat = parse_gpkg_point(geom_blob)
        if lon is None:
            print(f"Warning: Could not parse geometry for tree_id {tree_id}")
            continue

        if common_name is None:
            missing_count += 1

        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [lon, lat]
            },
            "properties": {
                "tree_id": tree_id,
                "common_name": common_name or "Unknown",
                "scientific_name": scientific_name or "Unknown",
                "family": family or "Unknown",
                "origin": origin or "Unknown"
            }
        }
        features.append(feature)

    conn.close()

    geojson = {
        "type": "FeatureCollection",
        "features": features
    }

    # Write to file
    print(f"Exporting {len(features)} trees to '{OUTPUT_GEOJSON}'...")
    with open(OUTPUT_GEOJSON, 'w') as f:
        json.dump(geojson, f, indent=2)

    print("Export complete!")

    if missing_count > 0:
        print(f"Warning: {missing_count} trees have no matching species record.")


if __name__ == "__main__":
    if not os.path.exists(GEOPACKAGE_PATH):
        print(f"Error: The file '{GEOPACKAGE_PATH}' was not found.")
    else:
        export_trees()
