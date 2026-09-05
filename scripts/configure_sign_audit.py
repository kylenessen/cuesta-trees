"""Configure observation forms, tree summaries, and the repeatable sign audit.

Run with uv run /Applications/QGIS.app/Contents/MacOS/qgis_process run
scripts/configure_sign_audit.py --PROJECT_PATH=map/cuesta-trees.qgz.
This script changes project configuration only, never observation records.
"""

import re
from collections import Counter
from pathlib import Path
from zipfile import ZipFile

from qgis.core import (
    QgsAttributeEditorField,
    QgsCategorizedSymbolRenderer,
    QgsDefaultValue,
    QgsEditorWidgetSetup,
    QgsField,
    QgsFieldConstraints,
    QgsLayerTreeModel,
    QgsMarkerSymbol,
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingParameterString,
    QgsRendererCategory,
)
from qgis.PyQt.QtCore import QMetaType

STATUS_VALUES = ("OK", "Needs Attention", "New Species", "Removed", "Other")
PRESENCE_VALUES = ("Present", "Absent", "Unknown")
VISIBLE_OBSERVATION_FIELDS = ("sign_presence", "status", "notes", "photo")
RETIRED_OBSERVATION_FIELDS = ("sign_status", "action_needed", "priority")
TREE_PREVIEW_FIELDS = (
    "scientific_name",
    "latest_sign_presence",
    "latest_status",
    "last_observed",
)
STATUS_COLORS = (
    ("OK", "#1b9e77"),
    ("Needs Attention", "#d73027"),
    ("New Species", "#8e44ad"),
    ("Removed", "#7f8c8d"),
    ("Other", "#2c7fb8"),
)
AUDIT_CATEGORIES = (
    ("Not Checked", "#f2c94c"),
    *STATUS_COLORS,
    ("Sign Absent", "#f46d43"),
    ("Sign Unknown", "#969696"),
)


def latest_observation_expression(field, condition="TRUE"):
    """Match the export's UUID, timestamp, then fid ordering."""
    return f"""
with_variable('uuid', "tree_uuid",
  with_variable('latest_date',
    aggregate('Observations', 'max', "dateobserved",
      filter := "tree_uuid" = @uuid AND ({condition})),
    with_variable('latest_fid',
      aggregate('Observations', 'max', "fid",
        filter := "tree_uuid" = @uuid AND ({condition})
          AND ("dateobserved" = @latest_date
            OR ("dateobserved" IS NULL AND @latest_date IS NULL))),
      attribute(get_feature('Observations', 'fid', @latest_fid), '{field}')
    )
  )
)""".strip()


AUDIT_EXPRESSION = f"""
with_variable('cutoff', to_datetime(@sign_audit_started),
  with_variable('eligible_presence',
    {latest_observation_expression("sign_presence", '"dateobserved" < @cutoff')},
    with_variable('current_presence', {latest_observation_expression("sign_presence")},
      with_variable('observed_at', {latest_observation_expression("dateobserved")},
        CASE
          WHEN coalesce(@eligible_presence, 'Unknown') <> 'Present' THEN 'Not in audit'
          WHEN @observed_at IS NULL OR @observed_at < @cutoff THEN 'Not Checked'
          WHEN {latest_observation_expression("status")} = 'Removed' THEN 'Removed'
          WHEN @current_presence = 'Absent' THEN 'Sign Absent'
          WHEN coalesce(@current_presence, 'Unknown') <> 'Present' THEN 'Sign Unknown'
          ELSE coalesce({latest_observation_expression("status")}, 'Other')
        END
      )
    )
  )
)""".strip()


def set_expression(layer, name, expression, field_type=QMetaType.Type.QString):
    index = layer.fields().indexOf(name)
    if index < 0:
        layer.addExpressionField(expression, QgsField(name, field_type))
    else:
        layer.updateExpressionField(index, expression)


def renderer(field, categories, hide_outside=False):
    values = []
    for value, color in categories:
        symbol = QgsMarkerSymbol.createSimple(
            {
                "name": "circle",
                "color": color,
                "size": "3.2",
                "outline_color": "#ffffff",
                "outline_width": "0.5",
            }
        )
        values.append(QgsRendererCategory(value, symbol, value))
    if hide_outside:
        symbol = QgsMarkerSymbol.createSimple({"name": "circle"})
        symbol.setOpacity(0.0)
        values.append(QgsRendererCategory("Not in audit", symbol, "Not in audit"))
    return QgsCategorizedSymbolRenderer(field, values)


def value_map(layer, field, values, alias):
    index = layer.fields().indexOf(field)
    if index < 0:
        raise QgsProcessingException(
            f"Missing {field}. Run the sign presence migration first."
        )
    layer.setEditorWidgetSetup(
        index, QgsEditorWidgetSetup("ValueMap", {"map": [{v: v} for v in values]})
    )
    layer.setFieldAlias(index, alias)
    layer.setFieldConstraint(
        index,
        QgsFieldConstraints.ConstraintNotNull,
        QgsFieldConstraints.ConstraintStrengthHard,
    )
    allowed = ", ".join(f"'{v}'" for v in values)
    layer.setConstraintExpression(
        index, f'"{field}" IN ({allowed})', f"Choose {alias.lower()}"
    )
    layer.setFieldConstraint(
        index,
        QgsFieldConstraints.ConstraintExpression,
        QgsFieldConstraints.ConstraintStrengthHard,
    )


def configure_observations(layer):
    value_map(layer, "sign_presence", PRESENCE_VALUES, "Sign Presence")
    value_map(layer, "status", STATUS_VALUES, "Observation Status")
    # Unknown is safe for a new visit. Do not silently inherit a prior sign.
    layer.setDefaultValueDefinition(
        layer.fields().indexOf("sign_presence"), QgsDefaultValue("'Unknown'", False)
    )
    layer.setDefaultValueDefinition(
        layer.fields().indexOf("status"),
        QgsDefaultValue(
            "coalesce(attribute(@parent, 'latest_status'), 'Other')", False
        ),
    )
    config = layer.editFormConfig()
    root = config.invisibleRootContainer()
    root.clear()
    for name in VISIBLE_OBSERVATION_FIELDS:
        root.addChildElement(
            QgsAttributeEditorField(name, layer.fields().indexOf(name), root)
        )
    for name in RETIRED_OBSERVATION_FIELDS:
        index = layer.fields().indexOf(name)
        if index >= 0:
            config.setReadOnly(index, True)
            layer.setDefaultValueDefinition(index, QgsDefaultValue())
    layer.setEditFormConfig(config)
    table = layer.attributeTableConfig()
    table.update(layer.fields())
    columns = table.columns()
    for column in columns:
        if column.name in RETIRED_OBSERVATION_FIELDS:
            column.hidden = True
    table.setColumns(columns)
    layer.setAttributeTableConfig(table)


def configure_tree_fields(layer):
    set_expression(layer, "latest_status", latest_observation_expression("status"))
    set_expression(
        layer, "latest_sign_presence", latest_observation_expression("sign_presence")
    )
    set_expression(
        layer,
        "last_observed",
        latest_observation_expression("dateobserved"),
        QMetaType.Type.QDateTime,
    )
    set_expression(layer, "sign_audit_status", AUDIT_EXPRESSION)
    for name, alias in (
        ("latest_status", "Latest Status"),
        ("latest_sign_presence", "Sign Presence"),
        ("last_observed", "Last Observed"),
    ):
        layer.setFieldAlias(layer.fields().indexOf(name), alias)
    config = layer.editFormConfig()
    root = config.invisibleRootContainer()
    # Rebuild the form to resolve stale numeric indexes while keeping its relation.
    children = [
        child.clone(root)
        for child in root.children()
        if not isinstance(child, QgsAttributeEditorField)
    ]
    root.clear()
    for name in (
        "latest_sign_presence",
        "latest_status",
        "last_observed",
        "tree_id",
        "common_name",
        "scientific_name",
        "family",
        "origin",
    ):
        index = layer.fields().indexOf(name)
        root.addChildElement(QgsAttributeEditorField(name, index, root))
        if name != "tree_id":
            config.setReadOnly(index, True)
    for child in children:
        root.addChildElement(child)
    layer.setEditFormConfig(config)
    layer.setMapTipTemplate("# fields\n" + "\n".join(TREE_PREVIEW_FIELDS))
    table = layer.attributeTableConfig()
    table.update(layer.fields())
    columns = table.columns()
    for column in columns:
        if column.name == "current_action":
            column.hidden = True
    table.setColumns(columns)
    layer.setAttributeTableConfig(table)


def map_theme_record(project):
    root = project.layerTreeRoot()
    return project.mapThemeCollection().createThemeFromCurrentState(
        root, QgsLayerTreeModel(root)
    )


class ConfigureSignAudit(QgsProcessingAlgorithm):
    AUDIT_START = "AUDIT_START"

    def name(self):
        return "configure_sign_audit"

    def displayName(self):
        return "Configure Cuesta sign audit"

    def group(self):
        return "Cuesta Trees"

    def groupId(self):
        return "cuesta_trees"

    def createInstance(self):
        return ConfigureSignAudit()

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterString(
                self.AUDIT_START,
                "Audit start date and time",
                defaultValue="",
                optional=True,
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        project = context.project()
        if project is None or not project.fileName():
            raise QgsProcessingException("Pass a QGIS project with --PROJECT_PATH")
        path = Path(project.fileName())
        trees = project.mapLayersByName("Tree Locations")[0]
        observations = project.mapLayersByName("Observations")[0]
        if not trees.isValid() or not observations.isValid():
            raise QgsProcessingException("Tree or observation layer is invalid")
        if observations.fields().indexOf("sign_presence") < 0:
            raise QgsProcessingException("Run migrate_sign_presence.py first")
        variables = project.customVariables()
        audit_start = self.parameterAsString(
            parameters, self.AUDIT_START, context
        ).strip() or variables.get("sign_audit_started", "2026-08-08 00:00:00")
        variables["sign_audit_started"] = audit_start
        project.setCustomVariables(variables)
        configure_observations(observations)
        styles = trees.styleManager()
        original_style = styles.currentStyle()
        styles.setCurrentStyle("default")
        configure_tree_fields(trees)
        trees.setRenderer(renderer("latest_status", (*STATUS_COLORS, ("", "#f2c94c"))))
        themes = project.mapThemeCollection()
        if themes.hasMapTheme("Tree Condition"):
            themes.removeMapTheme("Tree Condition")
        themes.insert("Tree Condition", map_theme_record(project))
        if "Sign Audit" in styles.styles():
            styles.removeStyle("Sign Audit")
        styles.addStyleFromLayer("Sign Audit")
        styles.setCurrentStyle("Sign Audit")
        configure_tree_fields(trees)
        trees.setRenderer(
            renderer("sign_audit_status", AUDIT_CATEGORIES, hide_outside=True)
        )
        if themes.hasMapTheme("Sign Audit"):
            themes.removeMapTheme("Sign Audit")
        themes.insert("Sign Audit", map_theme_record(project))
        styles.setCurrentStyle(
            original_style if original_style in styles.styles() else "default"
        )
        counts = Counter(str(f["sign_audit_status"]) for f in trees.getFeatures())
        if not project.write():
            raise QgsProcessingException(f"Could not save {path}")
        # QGIS may serialize this GPS setting as an absolute path.
        with ZipFile(path) as archive:
            entries = [
                (info, archive.read(info.filename)) for info in archive.infolist()
            ]
        with ZipFile(path, "w") as archive:
            for info, data in entries:
                if info.filename.endswith(".qgs"):
                    text = data.decode("utf-8")
                    text = re.sub(
                        r'destinationLayerSource="[^"]*cuesta-trees\.gpkg\|layername=tree_locations"',
                        'destinationLayerSource="./cuesta-trees.gpkg|layername=tree_locations"',
                        text,
                    )
                    data = text.encode("utf-8")
                archive.writestr(info, data)
        feedback.pushInfo(f"Audit status counts: {dict(sorted(counts.items()))}")
        return {
            "AUDIT_START": audit_start,
            "AUDIT_STATUS_COUNTS": dict(counts),
            "PROJECT": str(path),
        }
