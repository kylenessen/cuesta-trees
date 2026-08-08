# Cuesta Trees Field Workflow

The active QGIS and Mergin Maps project lives in `map/`. Open `map/cuesta-trees.qgz` when working in QGIS.

The mobile project should stay centered on tree points and observation records. In the field, tap a tree point and add an observation. Use that observation to record tree condition, sign condition, needed work, priority, notes, and a photo when useful.

The `tree_locations` layer is the map layer for physical tree locations. Keep it mostly stable. It should hold geometry, stable IDs, and display fields. Do not use it as the main place for ongoing notes or sign work.

The `observations` table is the main work log. Each visit, sign check, maintenance note, or tree health concern should be a new observation. This preserves history and lets reports query the most recent observation for each tree.

The `sign_inventory_current` table is still available as reference data. It should not be the primary field entry workflow. Most sign work can be captured as observations with `sign_status`, `action_needed`, `priority`, notes, and photo.

The old sign inventory is useful for order lists and audits. If orphan signs need field mapping later, create a small `orphan_signs` point layer rather than forcing them into `tree_locations`.

The basic field routine is simple. Open the tree point, add an observation, choose the tree status, choose the sign status, choose any needed action, set priority, add notes, and attach a photo if it helps.

## Sign audit campaigns

Use the `Sign Audit` map theme when checking signs. The project variable `sign_audit_started` defines the beginning of the current campaign. Trees whose latest status is `OK` or `Needs Attention` appear as `Not Checked` until they receive an observation after that date with a completed sign status. Trees with any other latest status are not part of the audit and are hidden by the audit style.

Record only real field visits as observations. Do not create bulk placeholder observations to reset the map. Starting a new audit requires changing `sign_audit_started` in the QGIS project variables, saving the project, and synchronizing it to Mergin Maps.

The configuration can be rebuilt from the command line with QGIS Processing. Replace the application path if a different QGIS installation is active.

```sh
/Applications/QGIS.app/Contents/MacOS/qgis_process run scripts/configure_sign_audit.py \
  --PROJECT_PATH=map/cuesta-trees.qgz \
  -- AUDIT_START='2026-08-08 00:00:00'
```
