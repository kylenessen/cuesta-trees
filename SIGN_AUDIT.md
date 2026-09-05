# Sign Audit Runbook

This guide explains how the sign audit works and how to start a new campaign. Use it at the beginning of each audit, after the previous field observations have been synchronized.

## How the audit works

The audit is controlled by the QGIS project variable `sign_audit_started`. Its value is the date and time when the current campaign began.

For each tree, QGIS finds its last observation before that cutoff. A tree enters the audit only when that observation recorded `sign_presence = Present`. Absent or unknown signs remain outside the audit, regardless of maintenance status. Timestamp ties are resolved by the highest observation `fid`.

A tree with no observation before the cutoff also remains outside the audit. This keeps newly added trees and other records without an established sign status out of the campaign.

An included tree displays as `Not Checked` when it has no observation on or after the cutoff. After a field visit, its newest observation controls its symbol. A removed tree displays as `Removed`. Otherwise, absent and unknown signs display as `Sign Absent` and `Sign Unknown`. A present sign displays its observation status, such as `OK` or `Needs Attention`.

`Not Checked` is calculated by QGIS. It is not stored as an observation. Starting a campaign does not insert, update, or delete any tree or observation records.

## Before starting a new campaign

Synchronize the desktop project and every field device with Mergin Maps. Confirm that no field edits are waiting to upload. Open the synchronized project once and make sure the recent observations are present.

Choose the campaign start date. Midnight at the beginning of the first audit day is usually clearest. Write it as `YYYY-MM-DD 00:00:00`.

Record the current observation count before the reset. This is an optional safety check, but it makes it easy to confirm that only project configuration changed.

```sh
sqlite3 map/cuesta-trees.gpkg \
  "SELECT count(*) AS observation_count FROM observations;"
```

Close QGIS before running the reset command.

## Start the campaign

Run the configuration script from the repository root. Replace the example date with the first day of the new campaign.

```sh
uv run /Applications/QGIS.app/Contents/MacOS/qgis_process run scripts/configure_sign_audit.py \
  --PROJECT_PATH=map/cuesta-trees.qgz \
  -- AUDIT_START='2027-08-01 00:00:00'
```

The script updates `sign_audit_started`, rebuilds the audit expression and styles, restores the two map themes, and configures the mobile forms and tree preview. It also prints the number of trees in each audit status.

The expected data change is none. Run the observation count command again and confirm that it matches the earlier count. A Git status check should normally show only `map/cuesta-trees.qgz` as changed.

```sh
git status --short
```

If the GeoPackage changed during this reset, stop and inspect it before synchronizing. The reset itself should not modify `map/cuesta-trees.gpkg`.

## Check the result in QGIS

Open `map/cuesta-trees.qgz` and select the `Sign Audit` map theme. Most included trees should now display as `Not Checked`.

Check at least one tree whose earlier sign presence was `Present`. It should be included. Check one whose earlier presence was `Absent` or `Unknown`. It should not appear in the audit theme.

Switch to the `Tree Condition` map theme and confirm that the normal map still works. Tap a tree and confirm that its preview shows Scientific Name, Sign Presence, Latest Status, and Last Observed.

## Synchronize to Mergin Maps

Review the Mergin project status in QGIS. The reset should show the QGIS project as the local change. Synchronize it to the server, then synchronize the field device.

On the field device, open the project and select the `Sign Audit` theme if it is not already active. Tap a known included tree and confirm that it displays as `Not Checked` before beginning field work.

Commit the project change and the updated Mergin metadata to Git after the synchronization is complete.

## Field workflow

Create one real observation for each tree you visit. The observation form asks for Sign Presence, Observation Status, Notes, and Photo. Set presence for the visit. It starts at `Unknown`. Saving automatically replaces the calculated `Not Checked` symbol with the appropriate sign or status category.

Do not bulk-create `Not Checked` observations. Do not change tree records merely to clear the audit symbol. Notes are the place for repair details, replacement needs, and other context.

## Quick reset in the QGIS interface

If the project configuration is already intact, the campaign can also be advanced in QGIS. Open Project Properties, open Variables, and change `sign_audit_started` to the new cutoff. Save the project and synchronize it.

The script is preferred because it also checks and repairs the styles, themes, forms, and mobile preview. Use the interface method only when those pieces are known to be working.

## Troubleshooting

If the map appears unchanged, confirm that you opened the project from this repository and selected the `Sign Audit` theme. On the phone, confirm that the latest Mergin version was downloaded.

If excluded trees appear, confirm the cutoff date and inspect their last observation before that cutoff. Eligibility is frozen from sign presence in that earlier observation. A later audit observation can still mark an included tree as removed or its sign as absent.

If every tree says `Not in audit`, check the cutoff format and make sure the observations are synchronized. Rerun the configuration script and review the printed status counts.

If the mobile preview shows raw fields such as `fid`, rerun the configuration script, save the project, and synchronize it again. The script restores the custom tree preview.

## Automated project validation

Run the read-only validator after changes to forms, styles, or expressions. It compares every tree summary and audit result with the GeoPackage, checks both themes, and verifies that a new observation defaults to unknown sign presence.

```sh
uv run /Applications/QGIS.app/Contents/MacOS/qgis_process run scripts/validate_qgis_project.py \
  --PROJECT_PATH=map/cuesta-trees.qgz
```

On the bundled macOS QGIS installation, set `PROJ_DATA=/Applications/QGIS.app/Contents/Resources/qgis/proj` if QGIS cannot find `proj.db`. For a headless check, also set `QT_QPA_PLATFORM=offscreen`.

Running the configuration script without `AUDIT_START` preserves the current campaign date. The September 2026 field migration is already applied. Do not rerun it to start an audit. For deploying that database schema change to devices, follow [FIELD_WORKFLOW.md](FIELD_WORKFLOW.md).
