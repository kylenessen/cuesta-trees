"""Configure the repeatable sign audit view in a QGIS project.

Run this script with qgis_process and pass the target project with
``--PROJECT_PATH``. The script changes project configuration only. It does not
insert or update tree or observation records.
"""

import os
import re
import tempfile
from collections import Counter
from html import escape
from pathlib import Path
from zipfile import ZipFile

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
from qgis.PyQt.QtCore import QMetaType

AUDIT_EXPRESSION = r"""
with_variable(
  'cutoff',
  to_datetime(@sign_audit_started),
  with_variable(
    'uuid',
    "tree_uuid",
    with_variable(
      'eligible_at',
      aggregate(
        'Observations',
        'max',
        "dateobserved",
        filter :=
          "tree_uuid" = @uuid
          AND "dateobserved" < @cutoff
      ),
      with_variable(
        'eligible_status',
        array_first(
          aggregate(
            'Observations',
            'array_agg',
            "status",
            filter :=
              "tree_uuid" = @uuid
              AND "dateobserved" = @eligible_at
          )
        ),
        with_variable(
          'checked_at',
          aggregate(
            'Observations',
            'max',
            "dateobserved",
            filter :=
              "tree_uuid" = @uuid
              AND "dateobserved" >= @cutoff
          ),
          CASE
            WHEN @eligible_status NOT IN ('OK', 'Needs Attention')
              THEN 'Not in audit'
            WHEN @checked_at IS NULL
              THEN 'Not Checked'
            ELSE
              array_first(
                aggregate(
                  'Observations',
                  'array_agg',
                  "status",
                  filter :=
                    "tree_uuid" = @uuid
                    AND "dateobserved" = @checked_at
                )
              )
          END
        )
      )
    )
  )
)
""".strip()


AUDIT_CATEGORIES = (
    ("Not Checked", "#f2c94c"),
    ("OK", "#1b9e77"),
    ("Needs Attention", "#d73027"),
    ("No Sign", "#f46d43"),
    ("New Species", "#8e44ad"),
    ("Removed", "#7f8c8d"),
    ("Other", "#2c7fb8"),
)

VISIBLE_OBSERVATION_FIELDS = ("status", "notes", "photo")
RETIRED_OBSERVATION_FIELDS = ("sign_status", "action_needed", "priority")


def read_project_archive(project_path):
    with ZipFile(project_path) as archive:
        entries = [(info, archive.read(info.filename)) for info in archive.infolist()]

    qgs_entries = [(info, data) for info, data in entries if info.filename.endswith(".qgs")]
    if len(qgs_entries) != 1:
        raise QgsProcessingException("The QGZ project must contain exactly one QGS file")

    qgs_info, qgs_data = qgs_entries[0]
    return entries, qgs_info.filename, qgs_data.decode("utf-8")


def write_project_archive(project_path, entries, qgs_name, qgs_text):
    project_path = Path(project_path)
    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{project_path.stem}-",
        suffix=".qgz",
        dir=project_path.parent,
    )
    os.close(file_descriptor)

    try:
        with ZipFile(temporary_name, "w") as archive:
            for info, data in entries:
                archive.writestr(info, qgs_text.encode("utf-8") if info.filename == qgs_name else data)
        os.replace(temporary_name, project_path)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)


def map_layer_xml(project_xml, layer_name):
    for match in re.finditer(r"  <maplayer\b.*?</maplayer>", project_xml, re.DOTALL):
        if f"<layername>{layer_name}</layername>" in match.group(0):
            return match
    raise QgsProcessingException(f"Could not find {layer_name} in the saved project XML")


def replace_project_variable(project_xml, variable_name, variable_value):
    names_match = re.search(
        r'(      <properties name="variableNames" type="QStringList">)(.*?)(      </properties>)',
        project_xml,
        re.DOTALL,
    )
    values_match = re.search(
        r'(      <properties name="variableValues" type="QStringList">)(.*?)(      </properties>)',
        project_xml,
        re.DOTALL,
    )
    if not names_match or not values_match:
        raise QgsProcessingException("Project variables are not stored as QStringList values")

    names = re.findall(r"<value>(.*?)</value>", names_match.group(2))
    values = re.findall(r"<value>(.*?)</value>", values_match.group(2))
    if len(names) != len(values):
        raise QgsProcessingException("Project variable names and values have different lengths")

    if variable_name in names:
        values[names.index(variable_name)] = variable_value
    else:
        names.append(variable_name)
        values.append(variable_value)

    def value_lines(items):
        return "\n" + "\n".join(
            f"        <value>{escape(item, quote=False)}</value>" for item in items
        ) + "\n"

    project_xml = project_xml.replace(
        names_match.group(0),
        names_match.group(1) + value_lines(names) + names_match.group(3),
        1,
    )
    project_xml = project_xml.replace(
        values_match.group(0),
        values_match.group(1) + value_lines(values) + values_match.group(3),
        1,
    )
    return project_xml


def make_gps_destination_portable(project_xml):
    portable_source = "./cuesta-trees.gpkg|layername=tree_locations"
    project_xml, replacement_count = re.subn(
        r'destinationLayerSource="[^"]*cuesta-trees\.gpkg\|layername=tree_locations"',
        f'destinationLayerSource="{portable_source}"',
        project_xml,
        count=1,
    )
    if replacement_count != 1:
        raise QgsProcessingException("Could not update the GPS destination layer path")
    return project_xml


def simplify_observation_form(project_xml):
    observation_match = map_layer_xml(project_xml, "Observations")
    observation_xml = observation_match.group(0)
    form_match = re.search(
        r"      <attributeEditorForm>.*?      </attributeEditorForm>",
        observation_xml,
        re.DOTALL,
    )
    if not form_match:
        raise QgsProcessingException("Could not find the Observations form layout")

    visible_widgets = []
    for field_name in VISIBLE_OBSERVATION_FIELDS:
        widget_match = re.search(
            rf'        <attributeEditorField\b[^>]*name="{field_name}".*?'
            r"        </attributeEditorField>",
            form_match.group(0),
            re.DOTALL,
        )
        if not widget_match:
            raise QgsProcessingException(
                f"Could not find the {field_name} widget in the Observations form"
            )
        visible_widgets.append(widget_match.group(0))

    simple_form = (
        "      <attributeEditorForm>\n"
        + "\n".join(visible_widgets)
        + "\n      </attributeEditorForm>"
    )
    observation_xml = observation_xml.replace(form_match.group(0), simple_form, 1)

    for field_name in RETIRED_OBSERVATION_FIELDS:
        observation_xml, default_count = re.subn(
            rf'<default applyOnUpdate="[01]" expression="[^"]*" field="{field_name}"/>',
            f'<default applyOnUpdate="0" expression="" field="{field_name}"/>',
            observation_xml,
            count=1,
        )
        observation_xml, editable_count = re.subn(
            rf'<field editable="[01]" name="{field_name}"/>',
            f'<field editable="0" name="{field_name}"/>',
            observation_xml,
            count=1,
        )
        observation_xml, column_count = re.subn(
            rf'<column hidden="[01]" name="{field_name}" type="field"',
            f'<column hidden="1" name="{field_name}" type="field"',
            observation_xml,
            count=1,
        )
        if (default_count, editable_count, column_count) != (1, 1, 1):
            raise QgsProcessingException(
                f"Could not retire every project setting for {field_name}"
            )

    return (
        project_xml[: observation_match.start()]
        + observation_xml
        + project_xml[observation_match.end() :]
    )


def merge_audit_configuration(original_xml, configured_xml, audit_start):
    original_tree_match = map_layer_xml(original_xml, "Tree Locations")
    configured_tree_match = map_layer_xml(configured_xml, "Tree Locations")
    original_tree = original_tree_match.group(0)
    configured_tree = configured_tree_match.group(0)

    configured_manager_match = re.search(
        r"      <map-layer-style-manager\b.*?</map-layer-style-manager>",
        configured_tree,
        re.DOTALL,
    )
    original_manager_match = re.search(
        r"      <map-layer-style-manager\b.*?</map-layer-style-manager>",
        original_tree,
        re.DOTALL,
    )
    if not configured_manager_match or not original_manager_match:
        raise QgsProcessingException("Could not find the Tree Locations style manager")

    configured_prefix = configured_tree[: configured_manager_match.start()]
    audit_field_match = re.search(
        r'^        <field .*name="sign_audit_status".*/>$',
        configured_prefix,
        re.MULTILINE,
    )
    if not audit_field_match:
        raise QgsProcessingException("Could not find the generated sign audit expression field")

    original_prefix = original_tree[: original_manager_match.start()]
    original_suffix = original_tree[original_manager_match.end() :]
    original_prefix = re.sub(
        r'\n        <field .*name="sign_audit_status".*/>',
        "",
        original_prefix,
    )
    if "      </expressionfields>" not in original_prefix:
        raise QgsProcessingException("Could not find Tree Locations expression fields")
    original_prefix = original_prefix.replace(
        "      </expressionfields>",
        audit_field_match.group(0) + "\n      </expressionfields>",
        1,
    )
    merged_tree = (
        original_prefix
        + configured_manager_match.group(0)
        + original_suffix
    )
    merged_xml = (
        original_xml[: original_tree_match.start()]
        + merged_tree
        + original_xml[original_tree_match.end() :]
    )

    merged_xml, default_count = re.subn(
        r'<default applyOnUpdate="0" expression="[^"]*" field="status"/>',
        '<default applyOnUpdate="0" expression="attribute(@parent, \'latest_status\')" field="status"/>',
        merged_xml,
        count=1,
    )
    if default_count != 1:
        raise QgsProcessingException("Could not update the observation status default")

    configured_themes_match = re.search(
        r"  <visibility-presets>.*?</visibility-presets>",
        configured_xml,
        re.DOTALL,
    )
    if not configured_themes_match:
        raise QgsProcessingException("Could not find the generated map themes")
    merged_xml, theme_count = re.subn(
        r"  <visibility-presets(?:/>|>.*?</visibility-presets>)",
        configured_themes_match.group(0),
        merged_xml,
        count=1,
        flags=re.DOTALL,
    )
    if theme_count != 1:
        raise QgsProcessingException("Could not replace the project map themes")

    configured_header = configured_xml.splitlines()[1]
    original_lines = merged_xml.splitlines()
    original_lines[1] = configured_header
    merged_xml = "\n".join(original_lines) + ("\n" if merged_xml.endswith("\n") else "")
    merged_xml = replace_project_variable(merged_xml, "sign_audit_started", audit_start)
    merged_xml = make_gps_destination_portable(merged_xml)
    return simplify_observation_form(merged_xml)


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

        project_path = Path(project.fileName())
        if project_path.suffix.lower() != ".qgz":
            raise QgsProcessingException("This configuration script requires a QGZ project")
        original_entries, original_qgs_name, original_xml = read_project_archive(project_path)

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
        _, _, configured_xml = read_project_archive(project_path)
        merged_xml = merge_audit_configuration(original_xml, configured_xml, audit_start)
        write_project_archive(
            project_path,
            original_entries,
            original_qgs_name,
            merged_xml,
        )

        feedback.pushInfo(f"Configured sign audit starting {audit_start}")
        feedback.pushInfo(f"Saved {project.fileName()}")
        return {
            "AUDIT_START": audit_start,
            "AUDIT_STATUS_COUNTS": dict(sorted(audit_counts.items())),
            "PROJECT": project.fileName(),
        }
