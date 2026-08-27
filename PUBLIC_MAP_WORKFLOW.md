# Public Tree Map Workflow

## Purpose

The GitHub Pages map is public facing. Every point shown there represents a
tree where a visitor should expect to find a sign. The map must therefore show
only trees whose current status is `OK`.

Trees with other statuses remain in the QGIS and Mergin project for field work
and maintenance. They do not belong on the public map.

## Source of truth

`map/cuesta-trees.gpkg` contains the source data.

`tree_locations` is the durable layer of physical tree points. Each point has
a stable `tree_uuid`. `observations` is the history table. Each observation is
linked to its tree point through the same `tree_uuid`.

The current status of a tree point is the `status` of its most recent linked
observation. Sort observations by `dateobserved` descending. Use `fid` as a
tie breaker when two observations have the same timestamp.

The QGIS `latest_status` expression follows this model. The GitHub Pages export
script, `scripts/export_trees.py`, uses the equivalent SQLite query. The
historical `sign_inventory_current` table must not be used to select public map
points.

## Public map rule

Export a tree point only when its latest observation has status `OK`.

Do not export points whose latest status is `Removed`, `Needs Attention`, `No
Sign`, `New Species`, or any other value. Do not export a point without a
linked observation.

This keeps the maintenance information internal while making the public map a
reliable guide to signed trees.

## Refresh and publish

First synchronize the current Mergin project into `map/cuesta-trees.gpkg`.
Then regenerate the public GeoJSON from the current observations.

```sh
uv run scripts/export_trees.py
```

Check the current status totals before publishing when needed.

```sql
WITH ranked_observations AS (
  SELECT
    tree_uuid,
    status,
    row_number() OVER (
      PARTITION BY tree_uuid
      ORDER BY dateobserved DESC, fid DESC
    ) AS latest_rank
  FROM observations
  WHERE tree_uuid IS NOT NULL AND tree_uuid <> ''
)
SELECT o.status, count(*) AS tree_points
FROM tree_locations AS t
JOIN ranked_observations AS o
  ON o.tree_uuid = t.tree_uuid AND o.latest_rank = 1
GROUP BY o.status
ORDER BY o.status;
```

The generated `trees.geojson` is the data consumed by `index.html`. Commit the
updated GeoPackage, export script, and GeoJSON together. Push `main`. GitHub
Pages publishes from the root of `main` at
<https://kylenessen.github.io/cuesta-trees/>.

GitHub Pages and browsers can cache the prior GeoJSON briefly. Use a hard
refresh when confirming a newly published map.
