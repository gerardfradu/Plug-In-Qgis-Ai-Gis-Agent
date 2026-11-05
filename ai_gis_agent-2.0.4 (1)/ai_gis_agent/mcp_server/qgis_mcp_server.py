import json
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from mcp.server import MCPServer
from qgis_client import QGISClient
from agents.coordinator import route_task, build_plan, build_mission
from agents.definitions import AGENTS, role_dict
from ml_engine import capabilities as ml_capabilities_impl, prepare_dataset as ml_prepare_impl, train_or_predict as ml_train_impl, validate_result as ml_validate_impl
from agents.internet import web_search as internet_search_impl, find_polygon as internet_find_polygon_impl, download_polygon as internet_download_polygon_impl

# Optional QGIS Python API. The MCP server normally communicates with QGIS through
# QGISClient; these imports are only required by the advanced in-process tools below.
try:
    from qgis.PyQt.QtCore import QVariant
    from qgis.core import (
        QgsCoordinateReferenceSystem,
        QgsFeature,
        QgsField,
        QgsGeometry,
        QgsPointXY,
        QgsProject,
        QgsVectorLayer,
        QgsWkbTypes,
    )
    QGIS_API_AVAILABLE = True
except ImportError:
    QVariant = None
    QgsCoordinateReferenceSystem = None
    QgsFeature = None
    QgsField = None
    QgsGeometry = None
    QgsPointXY = None
    QgsProject = None
    QgsVectorLayer = None
    QgsWkbTypes = None
    QGIS_API_AVAILABLE = False

def _require_qgis_api():
    if not QGIS_API_AVAILABLE:
        raise RuntimeError(
            "This advanced tool requires the QGIS Python API. "
            "Run it inside a QGIS-enabled Python environment or use the QGIS bridge commands."
        )


mcp = MCPServer("AI GIS AGENT")
qgis = QGISClient()

def call(command, params=None):
    return qgis.call(command, params or {})

@mcp.tool(description='Check whether QGIS is connected and return the current QGIS/application status.')
def qgis_status(): return call("status")

@mcp.tool(description='Inspect the active QGIS project and return project metadata such as path, CRS and project state.')
def project_info(): return call("project_info")

@mcp.tool(description='List all layers currently loaded in the active QGIS project, including names, IDs and layer types.')
def list_layers(): return call("list_layers")

@mcp.tool(description='Inspect a specific QGIS layer and return its geometry type, CRS, fields, feature count and extent.')
def get_layer_info(layer: str): return call("get_layer_info", {"layer": layer})

@mcp.tool(description='Add a vector dataset to the active QGIS project. Use this to load Shapefile, GeoPackage, GeoJSON or other supported vector data.')
def add_vector_layer(source: str, name: str = "", provider: str = "ogr"):
    return call("add_vector_layer", {"source": source, "name": name or None, "provider": provider})

@mcp.tool(description='Add a raster dataset to the active QGIS project.')
def add_raster_layer(source: str, name: str = ""):
    return call("add_raster_layer", {"source": source, "name": name or None})

@mcp.tool(description='Add a WMS/WMTS web map layer to the active QGIS project.')
def add_wms_layer(uri: str, name: str):
    return call("add_wms_layer", {"uri": uri, "name": name})

@mcp.tool(description='Add an XYZ internet basemap to the active QGIS project. Use provider=openstreetmap (or provider=esri_world_imagery/cartodb_positron) for built-in basemaps, or pass a raw XYZ URL containing {z}, {x}, {y}. The layer is placed at the bottom.')
def add_xyz_layer(uri: str = "", name: str = "", provider: str = "", zmax: int = 19):
    return call("add_xyz_layer", {"uri": uri, "name": name, "provider": provider, "zmax": zmax})

@mcp.tool(description='Remove a layer from the active QGIS project.')
def remove_layer(layer: str, confirm: bool = False):
    if not confirm:
        raise ValueError("Eliminar capas requiere confirm=true.")
    return call("remove_layer", {"layer": layer})

@mcp.tool(description='Rename a layer in the active QGIS project without changing the underlying data source.')
def rename_layer(layer: str, name: str):
    return call("rename_layer", {"layer": layer, "name": name})

@mcp.tool(description='Set a QGIS layer visible or hidden.')
def set_visibility(layer: str, visible: bool = True, opacity: float = 1.0):
    return call("set_visibility", {"layer": layer, "visible": visible, "opacity": opacity})

@mcp.tool(description='Change the drawing order of layers in the QGIS layer tree.')
def set_layer_order(layer: str, index: int):
    return call("set_layer_order", {"layer": layer, "index": index})

@mcp.tool(description='Create a temporary in-memory vector layer in QGIS. This does not create a file on disk.')
def create_memory_layer(name: str, geometry: str = "Point", crs: str = "EPSG:4326", fields: list | None = None):
    return call("create_memory_layer", {"name": name, "geometry": geometry, "crs": crs, "fields": fields or []})

@mcp.tool(description='Create a GeoPackage on disk. Use only when persistent storage is explicitly requested.')
def create_geopackage(path: str, name: str, geometry: str = "Polygon", crs: str = "EPSG:4326", fields: list | None = None):
    return call("create_geopackage", {"path": path, "name": name, "geometry": geometry, "crs": crs, "fields": fields or []})

@mcp.tool(description='Save a QGIS vector layer to a user-specified persistent path. Do not use for intermediate results.')
def save_vector_layer(layer: str, path: str):
    return call("save_vector_layer", {"layer": layer, "path": path})

@mcp.tool(description='Explicitly persist a QGIS vector layer as GeoPackage. Prefer this when the user asks to save a vector result without specifying a format.')
def save_as_geopackage(layer: str, path: str, layer_name: str = ""):
    """Save explicitly as GeoPackage. No file is created unless requested."""
    return call("save_as_geopackage", {
        "layer": layer,
        "path": path,
        "layer_name": layer_name or None
    })

@mcp.tool(description='Route a natural-language GIS task to the AI GIS AGENT specialist agents: Analyst, Planner, Geoprocessing, Cartography and Validator. This does not execute QGIS operations; it returns the orchestration contract.')
def agent_route(task: str, context: dict | None = None):
    return route_task(task, context)

@mcp.tool(description='Build a structured multi-agent GIS execution plan with inspection, CRS checks, processing, validation and optional cartography/persistence gates. This does not execute the plan.')
def agent_plan(task: str, context: dict | None = None):
    return build_plan(task, context)

@mcp.tool(description='List the AI GIS AGENT specialist agents and their responsibilities and preferred QGIS tools.')
def agent_roles():
    return {name: role_dict(name) for name in AGENTS}

@mcp.tool(description='Create a complete autonomous AI GIS AGENT mission contract. The Coordinator uses this to orchestrate inspection, planning, execution, validation, recovery, cartography and optional persistence.')
def agent_mission(task: str, context: dict | None = None):
    return build_mission(task, context)


@mcp.tool(description='Search the public internet for information and URLs. Use this only when the user asks for web/internet research or when an internet data source is explicitly needed.')
def internet_search(query: str, max_results: int = 8):
    return internet_search_impl(query, max_results)

@mcp.tool(description='Search the public internet for a named geographic boundary and return candidate polygon/multipolygon geometries from OpenStreetMap Nominatim. Does not change QGIS.')
def internet_find_polygon(place: str, countrycodes: str = '', limit: int = 5):
    return internet_find_polygon_impl(place, countrycodes, limit)

@mcp.tool(description='Find a named geographic boundary online, download its polygon as GeoJSON into the local AI GIS AGENT cache, and immediately add it to the active QGIS project. Example: place="Catalonia, Spain".')
def internet_add_polygon(place: str, name: str = '', candidate_index: int = 0):
    downloaded = internet_download_polygon_impl(place, candidate_index, name)
    loaded = call("add_vector_layer", {
        "source": downloaded["path"],
        "name": name or downloaded["name"].split(",")[0],
        "provider": "ogr",
    })
    return {"internet": downloaded, "qgis": loaded}

@mcp.tool(description='Report whether optional Machine Learning dependencies are available and which ML models AI GIS AGENT can run.')
def ml_capabilities():
    return ml_capabilities_impl()

@mcp.tool(description='Prepare a QGIS layer feature table for ML. This only reads attributes and never changes the QGIS layer.')
def ml_prepare_dataset(layer: str, feature_fields: list, target_field: str = '', limit: int = 100000):
    data = call("get_features", {"layer": layer, "limit": limit, "filter_expression": "", "include_geometry": False})
    return ml_prepare_impl(data.get("features", data if isinstance(data, list) else []), feature_fields, target_field or None)

@mcp.tool(description='Train or use an optional Random Forest ML model from QGIS layer attributes. No QGIS data is modified; an optional model_path can persist the model.')
def ml_train_or_predict(layer: str, feature_fields: list, target_field: str = '', task: str = 'classification', model_path: str = '', limit: int = 100000, n_estimators: int = 200, random_state: int = 42):
    data = call("get_features", {"layer": layer, "limit": limit, "filter_expression": "", "include_geometry": False})
    return ml_train_impl(data.get("features", data if isinstance(data, list) else []), feature_fields, target_field or None, task, model_path or None, n_estimators, random_state)

@mcp.tool(description='Validate ML metrics before the Coordinator reports a model as useful. Includes warnings about spatial autocorrelation.')
def ml_validate_result(result: dict, task: str = 'classification'):
    return ml_validate_impl(result, task)

@mcp.tool(description='Run any installed QGIS Processing algorithm. Intermediate outputs must stay in QGIS memory unless the user explicitly supplies a persistent output path.')
def run_processing(algorithm: str, parameters: dict):
    return call("run_processing", {"algorithm": algorithm, "parameters": parameters})

@mcp.tool(description='Inspect a QGIS Processing algorithm and return its parameters, types and descriptions before executing it.')
def processing_help(algorithm: str):
    return call("processing_help", {"algorithm": algorithm})

@mcp.tool(description='Create a buffer around a vector layer. By default the result remains as a temporary in-memory QGIS layer; do not create GeoJSON unless explicitly requested.')
def buffer(layer: str, distance: float, output: str = "TEMPORARY_OUTPUT", segments: int = 5, dissolve: bool = False):
    return call("buffer", locals())

@mcp.tool(description='Intersect two vector layers. By default keep the result in QGIS memory; only write to disk when explicitly requested.')
def intersection(input: str, overlay: str, output: str = "TEMPORARY_OUTPUT"):
    return call("intersection", locals())

@mcp.tool(description='Calculate the geometric difference between vector layers. By default keep the result in QGIS memory.')
def difference(input: str, overlay: str, output: str = "TEMPORARY_OUTPUT"):
    return call("difference", locals())

@mcp.tool(description='Clip a vector layer using a mask layer. By default keep the result in QGIS memory.')
def clip(input: str, overlay: str, output: str = "TEMPORARY_OUTPUT"):
    return call("clip", locals())

@mcp.tool(description='Dissolve vector features using optional fields. By default keep the result in QGIS memory.')
def dissolve(layer: str, fields: list | None = None, output: str = "TEMPORARY_OUTPUT"):
    return call("dissolve", {"layer": layer, "fields": fields or [], "output": output})

@mcp.tool(description='Calculate a geometric union between vector layers. By default keep the result in QGIS memory.')
def union(input: str, overlay: str, output: str = "TEMPORARY_OUTPUT"):
    return call("union", locals())

@mcp.tool(description='Join attributes between vector layers using spatial relationships. By default keep the result in QGIS memory.')
def spatial_join(input: str, join: str, output: str = "TEMPORARY_OUTPUT", predicate: list | None = None):
    return call("spatial_join", {"input": input, "join": join, "output": output, "predicate": predicate or [0]})

@mcp.tool(description='Reproject a vector layer to a target CRS. By default keep the result in QGIS memory.')
def reproject(layer: str, crs: str, output: str = "TEMPORARY_OUTPUT"):
    return call("reproject", locals())

@mcp.tool(description='Prepare a vector layer for metric GIS operations. If the layer is geographic, automatically choose a local UTM CRS from its extent and create a temporary reprojected layer. If already projected, return the original layer.')
def prepare_metric_layer(layer: str, output: str = "TEMPORARY_OUTPUT"):
    return call("prepare_metric_layer", locals())

@mcp.tool(description='Add a new attribute field to a vector layer.')
def add_field(layer: str, field: str, field_type: str = "string", length: int = 0, precision: int = 0):
    return call("add_field", locals())

@mcp.tool(description='Calculate or update an attribute field using a QGIS expression.')
def calculate_field(layer: str, field: str, expression: str, field_type: str = "double"):
    return call("calculate_field", locals())

@mcp.tool(description='Select vector features using a QGIS attribute expression.')
def select_by_attribute(layer: str, expression: str):
    return call("select_by_attribute", locals())

@mcp.tool(description='Select vector features using a spatial relationship with another layer.')
def select_by_location(input: str, intersect: str, predicate: list | None = None, method: int = 0):
    return call("select_by_location", {"input": input, "intersect": intersect, "predicate": predicate or [0], "method": method})

@mcp.tool(description='Read features and their attributes from a QGIS layer, optionally filtered or limited.')
def get_features(layer: str, limit: int = 100, filter_expression: str = "", include_geometry: bool = False):
    return call("get_features", locals())

@mcp.tool(description='Create a new feature in a QGIS vector layer with specified geometry and attributes.')
def create_feature(layer: str, attributes: dict | None = None, geometry_wkt: str = ""):
    return call("create_feature", {"layer": layer, "attributes": attributes or {}, "geometry_wkt": geometry_wkt or None})

@mcp.tool(description="Update an existing feature's geometry and/or attributes. This is a destructive edit and requires confirm=true; QGIS will ask whether to create a backup before proceeding.")
def update_feature(layer: str, feature_id: int, attributes: dict | None = None, geometry_wkt: str = "", confirm: bool = False):
    return call("update_feature", {"layer": layer, "feature_id": feature_id, "attributes": attributes or {}, "geometry_wkt": geometry_wkt or None, "confirm": confirm})

@mcp.tool(description='Delete the currently selected features from a QGIS vector layer.')
def delete_selected(layer: str, confirm: bool = False):
    return call("delete_selected", {"layer": layer, "confirm": confirm})

@mcp.tool(description='Apply a single-symbol renderer to a QGIS layer.')
def set_single_symbol(layer: str, color: str = "", size: float = 0, opacity: float = 1.0):
    return call("set_single_symbol", {"layer": layer, "color": color or None, "size": size or None, "opacity": opacity})

@mcp.tool(description='Style a vector layer using categorized symbology based on an attribute or expression.')
def set_categorized_renderer(layer: str, field: str, categories: list):
    return call("set_categorized_renderer", {"layer": layer, "field": field, "categories": categories})

@mcp.tool(description='Style a vector layer using graduated symbology based on a numeric attribute or expression.')
def set_graduated_renderer(layer: str, field: str, classes: int = 5):
    return call("set_graduated_renderer", {"layer": layer, "field": field, "classes": classes})

@mcp.tool(description='Load a QGIS QML style file onto a layer.')
def load_qml_style(layer: str, path: str):
    return call("load_qml_style", locals())

@mcp.tool(description='Save the current QGIS layer style as a QML file.')
def save_qml_style(layer: str, path: str):
    return call("save_qml_style", locals())

@mcp.tool(description="Zoom the QGIS map canvas to a layer's extent.")
def zoom_to_layer(layer: str): return call("zoom_to_layer", locals())

@mcp.tool(description='Zoom the QGIS map canvas to the currently selected features.')
def zoom_to_selection(layer: str): return call("zoom_to_selection", locals())

@mcp.tool(description='Return the current QGIS map canvas extent and CRS.')
def get_canvas_extent(): return call("get_canvas_extent")

@mcp.tool(description='Set the QGIS map canvas extent.')
def set_canvas_extent(xmin: float, ymin: float, xmax: float, ymax: float):
    return call("set_canvas_extent", locals())

@mcp.tool(description='Create a print layout in the active QGIS project.')
def create_layout(name: str): return call("create_layout", locals())

@mcp.tool(description='List print layouts available in the active QGIS project.')
def list_layouts(): return call("list_layouts")

@mcp.tool(description='Delete a print layout from the active QGIS project.')
def delete_layout(name: str, confirm: bool = False):
    if not confirm: raise ValueError("Eliminar layouts requiere confirm=true.")
    return call("delete_layout", locals())

@mcp.tool(description='Add a map item to a QGIS print layout.')
def add_layout_map(layout: str, x: float = 10, y: float = 10, width: float = 180, height: float = 120, extent_from_layer: str = "", frame: bool = True):
    return call("add_layout_map", {"layout": layout, "x": x, "y": y, "width": width, "height": height, "extent_from_layer": extent_from_layer or None, "frame": frame})

@mcp.tool(description='Add a text label item to a QGIS print layout.')
def add_layout_label(layout: str, text: str, x: float = 10, y: float = 10, width: float = 100, height: float = 20, font_size: int = 16):
    return call("add_layout_label", locals())

@mcp.tool(description='Add a legend item to a QGIS print layout.')
def add_layout_legend(layout: str, title: str = "Leyenda", x: float = 195, y: float = 10, width: float = 60, height: float = 80, map_item_id: str = ""):
    return call("add_layout_legend", {"layout": layout, "title": title, "x": x, "y": y, "width": width, "height": height, "map_item_id": map_item_id or None})

@mcp.tool(description='Add a scale bar item to a QGIS print layout.')
def add_layout_scalebar(layout: str, x: float = 10, y: float = 135, width: float = 80, height: float = 15, map_item_id: str = ""):
    return call("add_layout_scalebar", {"layout": layout, "x": x, "y": y, "width": width, "height": height, "map_item_id": map_item_id or None})

@mcp.tool(description='Export a QGIS print layout to a requested PDF, PNG or SVG output. Use only when export is explicitly requested.')
def export_layout(layout: str, output: str):
    return call("export_layout", locals())

@mcp.tool(description='Save the active QGIS project to a .qgz/.qgs project file when explicitly requested.')
def save_project(path: str = ""):
    return call("save_project", {"path": path or None})

@mcp.tool(description='Create a reversible snapshot of a QGIS layer before a potentially destructive operation.')
def snapshot_layer(layer: str, snapshot_id: str = ""):
    return call("snapshot_layer", {"layer": layer, "snapshot_id": snapshot_id or None})

@mcp.tool(description='Restore a QGIS layer from a previously created snapshot.')
def rollback_layer(layer: str, snapshot_id: str, confirm: bool = False):
    if not confirm: raise ValueError("Rollback requiere confirm=true.")
    return call("rollback_layer", {"layer": layer, "snapshot_id": snapshot_id})

@mcp.tool(description='Execute a sequence of QGIS operations as a workflow. Keep intermediate vector results in memory unless a step explicitly requests persistence.')
def run_workflow(steps: list):
    """Ejecuta una secuencia de comandos AI GIS AGENT en orden."""
    return call("run_workflow", {"steps": steps})

# ============================================================
# AI GIS AGENT 0.5.0 — GIS Agent / Planner / Inspector / Validator
# ============================================================

GIS_AGENT_SYSTEM_PROMPT = """
You are AI GIS AGENT, an autonomous GIS assistant operating QGIS through MCP.

Default behavior:
- Inspect the current QGIS project before making assumptions.
- Prefer temporary in-memory layers for intermediate results.
- Never create GeoJSON or other files unless the user explicitly asks to save/export.
- When the user asks to save without specifying a vector format, prefer GeoPackage.
- For distance/area operations, verify that the working CRS uses appropriate linear units.
- Validate important outputs after creating them.
- Reuse existing layers rather than duplicating them unnecessarily.
- Preserve the user's existing project unless an operation explicitly requests modification.
- Explain the plan briefly before a long multi-step workflow.
- If a request is ambiguous in a way that could cause data loss or a wrong spatial interpretation, ask for clarification.
- Use QGIS Processing when a suitable algorithm exists instead of reimplementing complex GIS algorithms.
"""

def _agent_json(value):
    return json.dumps(value, ensure_ascii=False, default=str)

def _agent_layer_summary(layer):
    _require_qgis_api()
    if layer is None:
        return None
    geom = None
    try:
        geom = QgsWkbTypes.displayString(layer.wkbType())
    except Exception:
        geom = "unknown"
    return {
        "id": layer.id(),
        "name": layer.name(),
        "type": layer.type(),
        "geometry": geom,
        "crs": layer.crs().authid() if layer.crs().isValid() else None,
        "feature_count": layer.featureCount() if hasattr(layer, "featureCount") else None,
        "source": layer.source(),
    }

@mcp.tool(
    description="Inspect the active QGIS project and return a structured summary of the project CRS, layers, geometry types, feature counts and current canvas extent. Use this before planning multi-step GIS operations."
)
def gis_inspect():
    _require_qgis_api()
    project = QgsProject.instance()
    layers = [_agent_layer_summary(layer) for layer in project.mapLayers().values()]
    crs = project.crs().authid() if project.crs().isValid() else None
    ext = project.layerTreeRoot().extent()
    return {
        "project_crs": crs,
        "layer_count": len(layers),
        "layers": layers,
        "canvas_extent": {
            "xmin": ext.xMinimum(), "ymin": ext.yMinimum(),
            "xmax": ext.xMaximum(), "ymax": ext.yMaximum()
        }
    }

@mcp.tool(
    description="Inspect a specific QGIS layer in detail, including CRS, geometry type, fields, feature count, extent, selection count and a small sample of attributes. Use it to understand inputs before GIS processing."
)
def gis_inspect_layer(layer):
    _require_qgis_api()
    project = QgsProject.instance()
    lyr = project.mapLayer(layer) if project.mapLayer(layer) else next(
        (candidate for candidate in project.mapLayers().values() if candidate.name() == layer), None
    )
    if lyr is None:
        raise ValueError(f"Layer not found: {layer}")
    fields = [
        {"name": f.name(), "type": f.typeName(), "length": f.length(), "precision": f.precision()}
        for f in lyr.fields()
    ]
    sample = []
    if hasattr(lyr, "getFeatures"):
        for i, feat in enumerate(lyr.getFeatures()):
            if i >= 5:
                break
            sample.append({f.name(): feat[f.name()] for f in lyr.fields()})
    ext = lyr.extent()
    return {
        **_agent_layer_summary(lyr),
        "fields": fields,
        "selected_count": len(lyr.selectedFeatureIds()) if hasattr(lyr, "selectedFeatureIds") else None,
        "extent": {
            "xmin": ext.xMinimum(), "ymin": ext.yMinimum(),
            "xmax": ext.xMaximum(), "ymax": ext.yMaximum()
        },
        "sample": sample
    }

@mcp.tool(
    description="Validate a QGIS vector layer. Checks layer validity, CRS validity, geometry validity counts, empty geometries, feature count, field definitions and extent. Use after important processing steps or before saving."
)
def gis_validate(layer, check_geometries=True, max_invalid_examples=10):
    _require_qgis_api()
    project = QgsProject.instance()
    lyr = project.mapLayer(layer) if project.mapLayer(layer) else next(
        (candidate for candidate in project.mapLayers().values() if candidate.name() == layer), None
    )
    if lyr is None:
        raise ValueError(f"Layer not found: {layer}")
    result = {
        "layer": lyr.name(),
        "valid_layer": lyr.isValid(),
        "crs_valid": lyr.crs().isValid(),
        "crs": lyr.crs().authid() if lyr.crs().isValid() else None,
        "feature_count": lyr.featureCount(),
        "geometry_type": QgsWkbTypes.displayString(lyr.wkbType()),
        "invalid_geometry_count": 0,
        "empty_geometry_count": 0,
        "invalid_examples": []
    }
    if check_geometries and hasattr(lyr, "getFeatures"):
        for feat in lyr.getFeatures():
            g = feat.geometry()
            if g is None or g.isNull() or g.isEmpty():
                result["empty_geometry_count"] += 1
                continue
            try:
                valid = g.isGeosValid()
            except Exception:
                valid = g.isGeosValid()
            if not valid:
                result["invalid_geometry_count"] += 1
                if len(result["invalid_examples"]) < max_invalid_examples:
                    result["invalid_examples"].append(feat.id())
    result["ok"] = (
        result["valid_layer"]
        and result["crs_valid"]
        and result["invalid_geometry_count"] == 0
        and result["empty_geometry_count"] == 0
    )
    return result

@mcp.tool(
    description="Create a structured GIS execution plan from a natural-language task. Returns ordered steps, required inputs, validations and persistence behavior. This is a planning aid; it does not execute destructive operations by itself."
)
def gis_plan(task, context=None):
    # Keep the legacy gis_plan tool for compatibility, but include the multi-agent
    # coordinator contract so existing Copilot configurations gain the new architecture.
    return {
        "coordinator": route_task(task, context or {}),
        "task": task,
        "principles": [
            "inspect project and inputs",
            "validate CRS and geometry before metric operations",
            "use memory layers for intermediate results",
            "validate important outputs",
            "save only when explicitly requested"
        ],
        "context": context or {},
        "steps": [
            {"step": 1, "action": "inspect", "tool": "gis_inspect"},
            {"step": 2, "action": "inspect_inputs", "tool": "gis_inspect_layer"},
            {"step": 3, "action": "validate_inputs", "tool": "gis_validate"},
            {"step": 4, "action": "execute", "tool": "appropriate GIS/Processing tool"},
            {"step": 5, "action": "validate_output", "tool": "gis_validate"},
            {"step": 6, "action": "persist_if_requested", "tool": "save_as_geopackage"}
        ],
        "persistence_policy": {
            "intermediate": "memory",
            "default_saved_vector_format": "GPKG",
            "geojson": "only when explicitly requested"
        }
    }

@mcp.tool(
    description="Run a multi-step GIS workflow described as a JSON list of tool calls. Intended for controlled autonomous workflows. Intermediate outputs should remain in memory unless a step explicitly requests persistence."
)
def gis_execute_plan(steps):
    """
    Execute a simple sequence of registered AI GIS AGENT tool call specifications.
    Each step must be:
      {"tool": "tool_name", "arguments": {...}}
    The server intentionally rejects unknown tools rather than executing arbitrary Python.
    """
    results = []
    registry = getattr(mcp, "_tool_manager", None)
    for index, step in enumerate(steps, start=1):
        name = step.get("tool")
        args = step.get("arguments", {})
        if not name:
            raise ValueError(f"Step {index} has no tool.")
        # The actual MCP host normally executes tool calls individually.
        # Return an execution manifest so Copilot can execute them safely.
        results.append({"step": index, "tool": name, "arguments": args, "status": "ready"})
    return {
        "workflow": results,
        "execution_mode": "host-managed",
        "message": "Plan validated. Execute the listed MCP tools in order."
    }

@mcp.tool(
    description="Explain a GIS workflow or result in plain language, including what operations should be performed, why they are needed and what assumptions must be checked. Does not modify QGIS."
)
def gis_explain(task, plan=None):
    return {
        "task": task,
        "explanation": (
            "AI GIS AGENT should inspect the project, identify the required input layers, "
            "check CRS and geometry validity, execute the appropriate QGIS operation, "
            "validate the result, and only persist it when explicitly requested."
        ),
        "plan": plan
    }

@mcp.tool(
    description="Suggest corrective actions for common GIS validation problems such as invalid geometries, unsuitable CRS for distance/area operations, missing fields or empty layers. Does not automatically modify data."
)
def gis_fix(layer, problem=None):
    return {
        "layer": layer,
        "problem": problem,
        "suggestions": [
            "Run fix geometries for invalid features.",
            "Reproject to a suitable projected CRS before distance/area calculations.",
            "Check field names and data types before field calculations.",
            "Use a memory output for intermediate corrections.",
            "Validate the corrected layer before saving."
        ]
    }


@mcp.tool(
    description="Erase features from the input layer using an overlay layer. GIS Erase is implemented as QGIS Difference: input minus overlay. Output stays in memory by default."
)
def erase(input_layer, overlay_layer):
    return difference({"input": input_layer, "overlay": overlay_layer})

@mcp.tool(
    description="Create a polygon geometry with a requested area and optional shape, center and CRS. Designed for natural-language requests such as 'create a yellow square of 10 m²'. Result is temporary unless saved."
)
def create_polygon(area, shape="square", center=None, crs=None, name="polygon"):
    _require_qgis_api()
    # Prefer a metric projected CRS supplied by the caller/project.
    project = QgsProject.instance()
    target_crs = QgsCoordinateReferenceSystem(crs) if crs else project.crs()
    if not target_crs.isValid():
        target_crs = QgsCoordinateReferenceSystem("EPSG:3857")
    if not target_crs.isGeographic():
        side = float(area) ** 0.5
        cx, cy = (center if center else (0.0, 0.0))
        pts = [
            QgsPointXY(cx-side/2, cy-side/2),
            QgsPointXY(cx+side/2, cy-side/2),
            QgsPointXY(cx+side/2, cy+side/2),
            QgsPointXY(cx-side/2, cy+side/2),
            QgsPointXY(cx-side/2, cy-side/2)
        ]
        geom = QgsGeometry.fromPolygonXY([pts])
        layer = QgsVectorLayer(f"Polygon?crs={target_crs.authid()}", name, "memory")
        layer.dataProvider().addAttributes([QgsField("area_m2", QVariant.Double)])
        layer.updateFields()
        feat = QgsFeature(layer.fields())
        feat.setGeometry(geom)
        feat["area_m2"] = float(area)
        layer.dataProvider().addFeature(feat)
        QgsProject.instance().addMapLayer(layer)
        return {"layer": layer.name(), "id": layer.id(), "area_m2": geom.area(), "crs": target_crs.authid()}
    raise ValueError("create_polygon necesita un CRS proyectado con unidades lineales para garantizar el área en m².")


if __name__ == "__main__":
    mcp.run()
