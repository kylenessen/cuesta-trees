#!/usr/bin/env python3
"""
Export Trees to GeoJSON

Exports tree locations with species information from the geopackage
to a GeoJSON file for use in the web map. Fetches photos from iNaturalist.

Uses only Python standard library (no geopandas required).

Usage: python scripts/export_trees.py
"""

import sqlite3
import struct
import json
import os
import urllib.request
import urllib.parse
import time

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


def fetch_inaturalist_photo(scientific_name):
    """
    Fetch the default photo URL for a species from iNaturalist.
    Returns the medium-sized photo URL or None if not found.
    """
    try:
        encoded_name = urllib.parse.quote(scientific_name)
        url = f"https://api.inaturalist.org/v1/taxa?q={encoded_name}&rank=species"

        req = urllib.request.Request(url, headers={
            'User-Agent': 'CuestaTreeMap/1.0 (educational project)'
        })

        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))

            if data.get('results'):
                # Find exact match for scientific name
                for taxon in data['results']:
                    if taxon.get('name', '').lower() == scientific_name.lower():
                        photo = taxon.get('default_photo')
                        if photo:
                            return photo.get('medium_url')

                # Fallback: use first result if no exact match
                first_result = data['results'][0]
                photo = first_result.get('default_photo')
                if photo:
                    return photo.get('medium_url')
    except Exception as e:
        print(f"  Warning: Could not fetch photo for '{scientific_name}': {e}")

    return None


def fetch_all_photos(scientific_names):
    """
    Fetch photos for all unique species names.
    Returns a dict mapping scientific_name -> photo_url
    """
    print(f"Fetching photos from iNaturalist for {len(scientific_names)} species...")
    photos = {}

    for i, name in enumerate(scientific_names):
        if name and name != "Unknown":
            print(f"  [{i+1}/{len(scientific_names)}] {name}...", end=" ", flush=True)
            photo_url = fetch_inaturalist_photo(name)
            if photo_url:
                photos[name] = photo_url
                print("OK")
            else:
                print("No photo")
            # Be respectful to the API
            time.sleep(0.1)

    print(f"Found photos for {len(photos)} species.")
    return photos


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

    # Get unique scientific names and fetch photos
    scientific_names = list(set(row[3] for row in rows if row[3]))
    photos = fetch_all_photos(scientific_names)

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

        # Get photo URL for this species
        photo_url = photos.get(scientific_name) if scientific_name else None

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
                "origin": origin or "Unknown",
                "photo_url": photo_url
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
