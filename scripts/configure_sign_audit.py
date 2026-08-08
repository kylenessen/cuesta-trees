"""Configure the repeatable sign audit view in a QGIS project.

Run this script with qgis_process and pass the target project with
``--PROJECT_PATH``. The script changes project configuration only. It does not
insert or update tree or observation records.
"""

from collections import Counter

from qgis.PyQt.QtCore import QMetaType
from qgis.core import (
    QgsCategorizedSymbolRenderer,
    QgsDefaultValue,
    QgsField,
    QgsLayerTreeModel,
    QgsMarkerSymbol,
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingParameterString,
    QgsRendererCategory,
)


AUDIT_EXPRESSION = r"""
with_variable(
  'cutoff',
  to_datetime(@sign_audit_started),
  with_variable(
    'uuid',
    "tree_uuid",
    with_variable(
      'checked_at',
      aggregate(
        'Observations',
        'max',
        "dateobserved",
        filter :=
          "tree_uuid" = @uuid
          AND "dateobserved" >= @cutoff
          AND coalesce("sign_status", '') NOT IN ('', 'Not Checked')
      ),
      CASE
        WHEN "latest_status" NOT IN ('OK', 'Needs Attention')
          THEN 'Not in audit'
        WHEN @checked_at IS NULL
          THEN 'Not Checked'
        ELSE
          array_first(
            aggregate(
              'Observations',
              'array_agg',
              "sign_status",
              filter :=
                "tree_uuid" = @uuid
                AND "dateobserved" = @checked_at
            )
          )
      END
    )
  )
)
""".strip()


AUDIT_CATEGORIES = (
    ("Not Checked", "#f2c94c"),
    ("Looks Good", "#1b9e77"),
    ("Missing", "#d73027"),
    ("Damaged", "#f46d43"),
    ("Incorrect Text", "#8e44ad"),
    ("Needs Install", "#2c7fb8"),
    ("Orphan Sign Nearby", "#8c6d31"),
    ("Other", "#666666"),
)


def marker_symbol(color):
    return QgsMarkerSymbol.createSimple(
        {
            "name": "circle",
            "color": color,
            "size": "3.2",
            "outline_color": "#ffffff",
            "outline_width": "0.5",
        }
    )


def audit_renderer():
    categories = [
        QgsRendererCategory(value, marker_symbol(color), value)
        for value, color in AUDIT_CATEGORIES
    ]
    hidden_symbol = marker_symbol("#000000")
    hidden_symbol.setOpacity(0.0)
    categories.append(QgsRendererCategory("Not in audit", hidden_symbol, "Not in audit"))
    return QgsCategorizedSymbolRenderer("sign_audit_status", categories)


def map_theme_record(project):
    root = project.layerTreeRoot()
    model = QgsLayerTreeModel(root)
    return project.mapThemeCollection().createThemeFromCurrentState(root, model)


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
                defaultValue="2026-08-08 00:00:00",
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        project = context.project()
        if project is None or not project.fileName():
            raise QgsProcessingException("Pass a QGIS project with --PROJECT_PATH")

        audit_start = self.parameterAsString(parameters, self.AUDIT_START, context).strip()
        if not audit_start:
            raise QgsProcessingException("AUDIT_START cannot be empty")

        tree_layers = project.mapLayersByName("Tree Locations")
        observation_layers = project.mapLayersByName("Observations")
        if len(tree_layers) != 1 or len(observation_layers) != 1:
            raise QgsProcessingException(
                "The project must contain one Tree Locations layer and one Observations layer"
            )

        tree_layer = tree_layers[0]
        observations = observation_layers[0]

        variables = project.customVariables()
        variables["sign_audit_started"] = audit_start
        project.setCustomVariables(variables)

        audit_field_index = tree_layer.fields().indexOf("sign_audit_status")
        if audit_field_index == -1:
            tree_layer.addExpressionField(
                AUDIT_EXPRESSION,
                QgsField("sign_audit_status", QMetaType.Type.QString),
            )
        else:
            tree_layer.updateExpressionField(audit_field_index, AUDIT_EXPRESSION)

        status_index = observations.fields().indexOf("status")
        if status_index == -1:
            raise QgsProcessingException("Observations is missing the status field")
        observations.setDefaultValueDefinition(
            status_index,
            QgsDefaultValue("attribute(@parent, 'latest_status')", False),
        )

        styles = tree_layer.styleManager()
        original_style = styles.currentStyle()
        if "Sign Audit" in styles.styles():
            styles.removeStyle("Sign Audit")
        styles.addStyleFromLayer("Sign Audit")
        styles.setCurrentStyle("Sign Audit")
        tree_layer.setRenderer(audit_renderer())
        tree_layer.triggerRepaint()
        styles.setCurrentStyle(original_style)

        themes = project.mapThemeCollection()
        for theme_name in ("Tree Condition", "Sign Audit"):
            if themes.hasMapTheme(theme_name):
                themes.removeMapTheme(theme_name)
        styles.setCurrentStyle(original_style)
        themes.insert("Tree Condition", map_theme_record(project))
        styles.setCurrentStyle("Sign Audit")
        themes.insert("Sign Audit", map_theme_record(project))
        styles.setCurrentStyle(original_style)

        audit_counts = Counter(
            str(feature["sign_audit_status"]) for feature in tree_layer.getFeatures()
        )
        feedback.pushInfo(f"Audit status counts: {dict(sorted(audit_counts.items()))}")

        project.setDirty(True)
        if not project.write():
            raise QgsProcessingException(f"Could not save {project.fileName()}")

        feedback.pushInfo(f"Configured sign audit starting {audit_start}")
        feedback.pushInfo(f"Saved {project.fileName()}")
        return {
            "AUDIT_START": audit_start,
            "AUDIT_STATUS_COUNTS": dict(sorted(audit_counts.items())),
            "PROJECT": project.fileName(),
        }
