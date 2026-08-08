# Cuesta Trees Field Workflow

The active QGIS and Mergin Maps project lives in `map/`. Open `map/cuesta-trees.qgz` when working in QGIS.

The mobile project should stay centered on tree points and observation records. In the field, tap a tree point and add an observation. The observation form contains only status, notes, and photo. Observer, date, and tree identifiers are filled automatically.

Tapping a tree shows its scientific name, latest observation status, and latest observation date. This mobile preview is configured through the Tree Locations HTML map tip in QGIS.

The `tree_locations` layer is the map layer for physical tree locations. Keep it mostly stable. It should hold geometry, stable IDs, and display fields. Do not use it as the main place for ongoing notes or sign work.

The `observations` table is the main work log. Each visit, sign check, maintenance note, or tree health concern should be a new observation. This preserves history and lets reports query the most recent observation for each tree. Use status for the overall result and notes for the specific problem or needed work.

The `sign_inventory_current` table is still available as reference data. It should not be the primary field entry workflow. Sign work is captured through the main observation status, with details in notes and a photo when useful.

The old sign inventory is useful for order lists and audits. If orphan signs need field mapping later, create a small `orphan_signs` point layer rather than forcing them into `tree_locations`.

The basic field routine is simple. Open the tree point, add an observation, choose the status, add notes, and attach a photo if it helps.

## Sign audit campaigns

Use the `Sign Audit` map theme when checking signs. The project variable `sign_audit_started` defines the beginning of the current campaign. Trees whose status at the start was `OK` or `Needs Attention` appear as `Not Checked` until they receive an observation after that date. The new observation status then controls the audit symbol. Trees that were already in another status when the campaign began are not part of the audit and are hidden by the audit style.

Record only real field visits as observations. Do not create bulk placeholder observations to reset the map.

Starting a new audit requires advancing `sign_audit_started`, checking the result, and synchronizing the project to Mergin Maps. Follow [SIGN_AUDIT.md](SIGN_AUDIT.md) for the annual reset procedure, validation steps, field workflow, and troubleshooting.
