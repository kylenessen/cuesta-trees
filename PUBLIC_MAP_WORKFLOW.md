# Public Tree Map Workflow

The public map shows physical tree locations with identifying signs or plaques. Sign repairs, overgrown vegetation, and incorrect sign text do not hide a signed tree.

## Source of truth

`map/cuesta-trees.gpkg` contains the source data. `tree_locations` stores physical points. Each observation in `observations` links to its point through `tree_uuid`. Tree numbers identify species and can be shared by multiple physical locations, so never use `tree_id` to decide which observation belongs to a point.

The latest observation is selected by `dateobserved` descending, then `fid` descending to resolve ties. Both the QGIS summary fields and `scripts/export_trees.py` follow this ordering. The historical `sign_inventory_current` table is reference material only.

## Visibility rule

Export a point only when its latest observation has `sign_presence = 'Present'`. Maintenance status does not affect visibility. `Absent`, `Unknown`, null values, and points without observations stay off the public map. An unknown latest observation does not fall back to an older present sign.

Sign presence has three values. `Present` means an identifying sign or plaque is physically at the tree, even if damaged, obscured, or inaccurate. `Absent` means it is missing or has been taken away. `Unknown` means the visit did not establish its presence.

The GeoJSON includes public tree information and photo URLs. Observation notes, maintenance status, and other working fields are not exported. Unsigned locations remain in QGIS and Mergin Maps.

## Refresh and publish

Synchronize field observations into the local project, then run the exporter.

```sh
uv run scripts/export_trees.py
```

Existing photo URLs are preserved. Add `--fetch-photos` to retrieve species photos for newly included trees.

Check visibility totals when needed.

```sql
WITH ranked AS (
  SELECT tree_uuid, sign_presence,
    row_number() OVER (
      PARTITION BY tree_uuid ORDER BY dateobserved DESC, fid DESC
    ) AS latest_rank
  FROM observations
  WHERE tree_uuid IS NOT NULL AND tree_uuid <> ''
)
SELECT o.sign_presence, count(*) AS tree_points
FROM tree_locations AS t
LEFT JOIN ranked AS o
  ON o.tree_uuid = t.tree_uuid AND o.latest_rank = 1
GROUP BY o.sign_presence;
```

Run export regression checks with `uv run -m unittest discover -s scripts`. Run the QGIS validation command in [SIGN_AUDIT.md](SIGN_AUDIT.md) after changing forms or expressions.

Commit the updated source GeoPackage and `trees.geojson`. Push `main`. GitHub Pages publishes the root of `main` at [the public tree map](https://kylenessen.github.io/cuesta-trees/). Check the deployed GeoJSON against the local file. A hard refresh may be needed while browser caches expire.

## September 2026 migration

The reviewed migration added sign presence to all 177 existing observations without changing their dates, notes, or locations. The expected public map has 75 points, up from 65. Nine signed `Needs Attention` locations and tree 67's identifying plaque were restored. The locations where signs were taken away remain hidden.

[The migration log](reference/sign_presence_migration_20260904.csv) records previous status, revised status, sign presence, and the reason for each classification. `scripts/migrate_sign_presence.py` applies this historical migration only once. Do not use it to interpret future field notes.

Adding a database field changes the Mergin schema. Follow the deployment steps in [FIELD_WORKFLOW.md](FIELD_WORKFLOW.md) before updating field devices.
