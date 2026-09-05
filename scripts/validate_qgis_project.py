"""Read-only QGIS checks for sign presence, forms, themes, and audit results.

Run through qgis_process with --PROJECT_PATH, using the same command as the
configuration script. It never saves the project or commits layer edits.
"""

import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from qgis.core import (
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsVectorLayerUtils,
)


class ValidateProject(QgsProcessingAlgorithm):
    def name(self):
        return "validate_cuesta_project"

    def displayName(self):
        return "Validate Cuesta project"

    def group(self):
        return "Cuesta Trees"

    def groupId(self):
        return "cuesta_trees"

    def createInstance(self):
        return ValidateProject()

    def initAlgorithm(self, config=None):
        pass

    def processAlgorithm(self, parameters, context, feedback):
        project = context.project()
        trees = project.mapLayersByName("Tree Locations")[0]
        observations = project.mapLayersByName("Observations")[0]
        package = Path(project.fileName()).parent / "cuesta-trees.gpkg"
        with sqlite3.connect(f"{package.resolve().as_uri()}?mode=ro", uri=True) as connection:
            connection.row_factory = sqlite3.Row
            history = connection.execute(
                "SELECT * FROM observations ORDER BY dateobserved DESC, fid DESC"
            ).fetchall()
        latest = {}
        before = {}
        cutoff = datetime.fromisoformat(
            project.customVariables()["sign_audit_started"]
        ).astimezone()
        for row in history:
            if not row["tree_uuid"]:
                continue
            latest.setdefault(row["tree_uuid"], row)
            if row["dateobserved"]:
                observed = datetime.fromisoformat(
                    row["dateobserved"].replace("Z", "+00:00")
                )
                if observed.tzinfo is None:
                    observed = observed.replace(tzinfo=timezone.utc)
                if observed < cutoff:
                    before.setdefault(row["tree_uuid"], row)
        counts = Counter()
        for feature in trees.getFeatures():
            row = latest.get(feature["tree_uuid"])
            if row is None:
                continue
            for field, source in (
                ("latest_sign_presence", "sign_presence"),
                ("latest_status", "status"),
            ):
                if feature[field] != row[source]:
                    raise QgsProcessingException(
                        f"Point {feature['point_id']} has inconsistent {field}"
                    )
            eligible = before.get(feature["tree_uuid"])
            if eligible is None or eligible["sign_presence"] != "Present":
                expected = "Not in audit"
            elif eligible["fid"] == row["fid"]:
                expected = "Not Checked"
            elif row["status"] == "Removed":
                expected = "Removed"
            elif row["sign_presence"] == "Absent":
                expected = "Sign Absent"
            elif row["sign_presence"] != "Present":
                expected = "Sign Unknown"
            else:
                expected = row["status"] or "Other"
            if feature["sign_audit_status"] != expected:
                raise QgsProcessingException(
                    f"Point {feature['point_id']} audit is {feature['sign_audit_status']}, expected {expected}"
                )
            counts[expected] += 1
        form_names = [
            child.name()
            for child in observations.editFormConfig()
            .invisibleRootContainer()
            .children()
        ]
        assert form_names == ["sign_presence", "status", "notes", "photo"], form_names
        new_visit = QgsVectorLayerUtils.createFeature(observations)
        assert new_visit["sign_presence"] == "Unknown", new_visit.attributes()
        for field in ("sign_presence", "status"):
            widget = observations.editorWidgetSetup(
                observations.fields().indexOf(field)
            )
            assert widget.type() == "ValueMap"
            assert not any("No Sign" in item for item in widget.config()["map"])
        original_style = trees.styleManager().currentStyle()
        for name, attribute in (
            ("default", "latest_status"),
            ("Sign Audit", "sign_audit_status"),
        ):
            trees.styleManager().setCurrentStyle(name)
            assert trees.renderer().classAttribute() == attribute
            form_names = [
                child.name()
                for child in trees.editFormConfig().invisibleRootContainer().children()
            ]
            assert (
                "latest_sign_presence" in form_names
                and "current_action" not in form_names
            )
            assert "latest_sign_presence" in trees.mapTipTemplate()
        trees.styleManager().setCurrentStyle(original_style)
        themes = project.mapThemeCollection()
        assert (
            themes.mapThemeStyleOverrides("Tree Condition")[trees.id()]
            != themes.mapThemeStyleOverrides("Sign Audit")[trees.id()]
        )
        feedback.pushInfo(
            f"Verified {sum(counts.values())} points against SQLite, new observation defaults, forms, and both styles. Audit counts {dict(counts)}"
        )
        return {"POINTS_VERIFIED": sum(counts.values())}
