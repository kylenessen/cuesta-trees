"""Export confirmed Cuesta tree locations for the GitHub Pages map.

Only locations whose sign inventory is marked ``Installed`` are exported. By
default, photo URLs already in the GeoJSON file are retained. Pass
``--fetch-photos`` to look up photos for any newly added trees.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import struct
import time
import urllib.parse
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PACKAGE = PROJECT_ROOT / "map" / "cuesta-trees.gpkg"
DEFAULT_OUTPUT = PROJECT_ROOT / "trees.geojson"


def parse_gpkg_point(blob: bytes | None) -> tuple[float | None, float | None]:
    """Return longitude and latitude from a GeoPackage point geometry."""
    if blob is None or blob[:2] != b"GP":
        return None, None

    envelope_type = (blob[3] >> 1) & 0x07
    envelope_sizes = {0: 0, 1: 32, 2: 48, 3: 48, 4: 64}
    wkb = blob[8 + envelope_sizes.get(envelope_type, 0) :]
    if len(wkb) < 21:
        return None, None

    byte_order = "<" if wkb[0] == 1 else ">"
    return struct.unpack(f"{byte_order}dd", wkb[5:21])


def existing_photo_urls(output_path: Path) -> dict[int, str]:
    """Read the existing site data as a local photo URL cache."""
    if not output_path.exists():
        return {}

    with output_path.open(encoding="utf-8") as output_file:
        data = json.load(output_file)
    return {
        feature["properties"]["tree_id"]: feature["properties"]["photo_url"]
        for feature in data.get("features", [])
        if feature["properties"].get("photo_url")
    }


def fetch_inaturalist_photo(scientific_name: str) -> str | None:
    """Fetch a medium-sized iNaturalist taxon photo URL."""
    try:
        query = urllib.parse.quote(scientific_name)
        request = urllib.request.Request(
            f"https://api.inaturalist.org/v1/taxa?q={query}&rank=species",
            headers={"User-Agent": "CuestaTreeMap/1.0 (educational project)"},
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            results = json.loads(response.read().decode("utf-8")).get("results", [])
    except OSError as error:
        print(f"Could not fetch a photo for {scientific_name}. {error}")
        return None

    exact_match = next(
        (
            item
            for item in results
            if item.get("name", "").casefold() == scientific_name.casefold()
        ),
        results[0] if results else None,
    )
    if exact_match and exact_match.get("default_photo"):
        return exact_match["default_photo"].get("medium_url")
    return None


def confirmed_tree_rows(package_path: Path) -> list[sqlite3.Row]:
    with sqlite3.connect(package_path) as connection:
        connection.row_factory = sqlite3.Row
        return connection.execute(
            """
            SELECT
                t.tree_id,
                t.geom,
                s.common_name,
                s.scientific_name,
                s.family,
                s.origin
            FROM tree_locations AS t
            JOIN sign_inventory_current AS si ON si.point_id = t.point_id
            LEFT JOIN species_master_current AS s ON s.tree_id = t.tree_id
            WHERE si.sign_status = 'Installed'
            ORDER BY t.tree_id
            """
        ).fetchall()


def export_trees(package_path: Path, output_path: Path, fetch_photos: bool) -> int:
    """Write confirmed mapped trees to a GeoJSON FeatureCollection."""
    rows = confirmed_tree_rows(package_path)
    cached_photos = existing_photo_urls(output_path)
    features = []

    for row in rows:
        longitude, latitude = parse_gpkg_point(row["geom"])
        if longitude is None or latitude is None:
            print(
                f"Skipping tree {row['tree_id']}. Its point geometry could not be read."
            )
            continue

        photo_url = cached_photos.get(row["tree_id"])
        if fetch_photos and not photo_url and row["scientific_name"]:
            photo_url = fetch_inaturalist_photo(row["scientific_name"])
            time.sleep(0.1)

        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [longitude, latitude]},
                "properties": {
                    "tree_id": row["tree_id"],
                    "common_name": row["common_name"] or "Unknown",
                    "scientific_name": row["scientific_name"] or "Unknown",
                    "family": row["family"] or "Unknown",
                    "origin": row["origin"] or "Unknown",
                    "photo_url": photo_url,
                },
            }
        )

    with output_path.open("w", encoding="utf-8") as output_file:
        json.dump(
            {"type": "FeatureCollection", "features": features}, output_file, indent=2
        )
        output_file.write("\n")

    print(f"Exported {len(features)} confirmed tree locations to {output_path}.")
    return len(features)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, default=DEFAULT_PACKAGE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--fetch-photos",
        action="store_true",
        help="Look up iNaturalist photos that are not already in the GeoJSON file.",
    )
    arguments = parser.parse_args()
    export_trees(arguments.package, arguments.output, arguments.fetch_photos)


if __name__ == "__main__":
    main()
