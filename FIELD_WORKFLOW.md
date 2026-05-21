# Cuesta Trees Field Workflow

The active QGIS and Mergin Maps project lives in `map/`. Open `map/cuesta-trees.qgz` when working in QGIS.

The mobile project should stay centered on tree points and observation records. In the field, tap a tree point and add an observation. Use that observation to record tree condition, sign condition, needed work, priority, notes, and a photo when useful.

The `tree_locations` layer is the map layer for physical tree locations. Keep it mostly stable. It should hold geometry, stable IDs, and display fields. Do not use it as the main place for ongoing notes or sign work.

The `observations` table is the main work log. Each visit, sign check, maintenance note, or tree health concern should be a new observation. This preserves history and lets reports query the most recent observation for each tree.

The `sign_inventory_current` table is still available as reference data. It should not be the primary field entry workflow. Most sign work can be captured as observations with `sign_status`, `action_needed`, `priority`, notes, and photo.

The old sign inventory is useful for order lists and audits. If orphan signs need field mapping later, create a small `orphan_signs` point layer rather than forcing them into `tree_locations`.

The basic field routine is simple. Open the tree point, add an observation, choose the tree status, choose the sign status, choose any needed action, set priority, add notes, and attach a photo if it helps.
