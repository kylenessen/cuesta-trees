# Cuesta Trees Field Workflow

The active QGIS and Mergin Maps project lives in `map/`. Open `map/cuesta-trees.qgz` in QGIS.

Tap a tree and add an observation for each real visit. The form shows Sign Presence, Observation Status, Notes, and Photo. Observer, date, and tree identifiers are filled automatically. The tree preview shows scientific name, latest sign presence, latest status, and last observed date.

## Sign presence and status

Choose `Present` when an identifying sign or plaque is at the tree. It still counts when screws are missing, vegetation obscures it, or its text needs correction. Choose `Absent` when no sign is there, including when you take one away for repair. Choose `Unknown` when you did not establish whether a sign is present.

A new observation starts with `Unknown` so an earlier sign is never silently carried forward as a new confirmation. Set presence for the current visit. Unknown observations hide that location from the public map until presence is confirmed again.

Use `OK` when there is no outstanding issue. Use `Needs Attention` for repairs, missing signs, vegetation, placement, or identification questions. Use `New Species` for a new inventory candidate, `Removed` when the tree is gone, and `Other` when the result does not fit those categories. `No Sign` is no longer a status because presence records that information directly. Notes hold the specific problem and needed work. The public map uses sign presence alone.

When a tree has been removed, record its sign as `Absent` if it is gone too, or `Unknown` if you did not check. Do not assume a past sign is still present. If a sign remains without its tree, record that orphan sign in notes for follow-up.

The `tree_locations` layer holds durable geometry and identifiers. The `observations` table is the work history. Do not use tree points as the main place for ongoing notes. Correct classification mistakes in the actual observation rather than adding a fictitious field visit. Preserve the original visit date and notes.

The `sign_inventory_current` table remains available for historical reference and order lists. Its fields and the retired observation fields `sign_status`, `action_needed`, and `priority` do not control current visibility. The retired fields are retained for history and hidden from the field form.

## Sign audit campaigns

The `Sign Audit` theme selects trees whose last observation before `sign_audit_started` recorded a present sign. Included trees appear as `Not Checked` until a real observation is recorded during the campaign. Current sign presence and status then control their audit symbols. The `Tree Condition` theme shows normal observation status for all working locations, including unsigned trees.

Do not create bulk placeholder observations to reset the map. Follow [SIGN_AUDIT.md](SIGN_AUDIT.md) to advance the campaign and validate the result.

## Deploying the new sign presence field to Mergin Maps

Adding `sign_presence` changes the database schema. Before deploying, synchronize all existing field-device edits using the old schema and verify the server contains them. If new observations arrive, incorporate them into the source data and review their sign presence before publishing the revised project.

After all edits are safe, remove the old local project from field devices, upload the revised desktop project to the same Mergin project, and freshly download it on each device. Verify that a new observation shows the presence dropdown before collecting more data. Do not upload edits made against an old schema after deployment. These steps follow [Mergin Maps guidance for revised projects](https://merginmaps.com/docs/manage/deploy-new-project/).

The GitHub Pages map and Mergin Maps deploy separately. Pushing Git commits publishes the public map. It does not synchronize the mobile project.

The sign presence revision was deployed to `mergin/cuesta-trees` as version `v55` on September 4, 2026. Server version `v54` was downloaded first and matched the source data used for the migration. A fresh download of `v55` passed QGIS validation for all 103 locations and preserved all 177 observations. Desktop synchronization reports no changes. Existing field-device copies must be replaced with a fresh download before further data collection.
