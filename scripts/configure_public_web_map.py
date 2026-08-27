"""Limit the public map to tree points with confirmed installed signs.

The source inventory is kept intact. This script only updates the Tree Locations
layer source in the QGIS project so Mergin Maps web maps render currently
confirmed tree locations.
"""

from __future__ import annotations

import argparse
import os
import re
import sqlite3
import tempfile
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


def checked_tree_point_ids(package_path: Path) -> tuple[int, list[int]]:
    with sqlite3.connect(package_path) as connection:
        installed_count = connection.execute(
            "SELECT count(*) FROM sign_inventory_current WHERE sign_status = 'Installed'"
        ).fetchone()[0]
        mappable_rows = connection.execute(
            """
            SELECT DISTINCT t.point_id
            FROM tree_locations AS t
            JOIN sign_inventory_current AS s ON s.point_id = t.point_id
            WHERE s.sign_status = 'Installed'
            ORDER BY t.point_id
            """
        ).fetchall()

    mappable_ids = [int(row[0]) for row in mappable_rows if row[0] is not None]
    return installed_count, mappable_ids


def update_project(project_path: Path, point_ids: list[int]) -> None:
    with ZipFile(project_path) as archive:
        entries = [(info, archive.read(info.filename)) for info in archive.infolist()]

    qgs_entries = [(info, data) for info, data in entries if info.filename.endswith(".qgs")]
    if len(qgs_entries) != 1:
        raise ValueError("The QGZ project must contain exactly one QGS file.")

    qgs_info, qgs_data = qgs_entries[0]
    qgs_text = qgs_data.decode("utf-8")
    tree_layers = [
        match
        for match in re.finditer(r"    <maplayer\b.*?</maplayer>", qgs_text, re.DOTALL)
        if "<layername>Tree Locations</layername>" in match.group(0)
    ]
    if len(tree_layers) != 1:
        raise ValueError("Could not find the Tree Locations layer.")
    tree_layer = tree_layers[0]

    subset = ', '.join(str(point_id) for point_id in point_ids)
    replacement_source = (
        "./cuesta-trees.gpkg|layername=tree_locations"
        f'|subset="point_id" IN ({subset})'
    )
    updated_layer, replacement_count = re.subn(
        r"<datasource>.*?</datasource>",
        f"<datasource>{replacement_source}</datasource>",
        tree_layer.group(0),
        count=1,
        flags=re.DOTALL,
    )
    if replacement_count != 1:
        raise ValueError("The Tree Locations layer has no data source.")
    updated_qgs = (
        qgs_text[: tree_layer.start()]
        + updated_layer
        + qgs_text[tree_layer.end() :]
    )
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{project_path.stem}-", suffix=".qgz", dir=project_path.parent
    )
    os.close(descriptor)
    try:
        with ZipFile(temporary_name, "w", ZIP_DEFLATED) as archive:
            for info, data in entries:
                archive.writestr(
                    info, updated_qgs if info.filename == qgs_info.filename else data
                )
        os.replace(temporary_name, project_path)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--package",
        type=Path,
        default=Path("map/cuesta-trees.gpkg"),
        help="GeoPackage containing the sign inventory and tree locations.",
    )
    parser.add_argument(
        "--project",
        type=Path,
        default=Path("map/cuesta-trees.qgz"),
        help="QGIS project used by the web map.",
    )
    arguments = parser.parse_args()

    installed_count, mappable_ids = checked_tree_point_ids(arguments.package)
    if not mappable_ids:
        raise ValueError("No installed signs have matching tree locations.")

    update_project(arguments.project, mappable_ids)
    missing_count = installed_count - len(mappable_ids)
    print(f"Filtered the web map to {len(mappable_ids)} checked tree locations.")
    if missing_count:
        print(f"{missing_count} installed sign has no matching tree location and is not shown.")


if __name__ == "__main__":
    main()
