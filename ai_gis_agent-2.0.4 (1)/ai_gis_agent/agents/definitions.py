"""Specialist definitions used by the AI GIS AGENT Coordinator."""
AGENTS = {
    "coordinator": {"description": "Orchestrates the mission, delegates work, manages state and recovery.", "tools": ["agent_route", "agent_plan", "agent_mission", "agent_roles"]},
    "analyst": {"description": "Inspects the QGIS project, resolves layers/fields/CRS and understands the GIS context.", "tools": ["gis_inspect", "gis_inspect_layer", "get_layer_info", "list_layers", "get_features"]},
    "planner": {"description": "Turns natural-language GIS goals into explicit, ordered, testable operations.", "tools": ["agent_plan", "processing_help", "gis_explain"]},
    "geoprocessing": {"description": "Executes vector/raster/Processing operations while keeping intermediates in memory.", "tools": ["run_processing", "buffer", "intersection", "difference", "clip", "dissolve", "union", "spatial_join", "reproject"]},
    "cartography": {"description": "Creates readable symbology, map canvas states and print layouts/exports.", "tools": ["set_single_symbol", "set_categorized_renderer", "set_graduated_renderer", "create_layout", "add_layout_map", "add_layout_legend", "add_layout_scalebar", "export_layout"]},
    "validator": {"description": "Checks geometry, CRS, feature counts, outputs and presentation; triggers recovery when needed.", "tools": ["gis_validate", "gis_fix", "gis_inspect_layer", "ml_validate_result"]},
    "ml": {"description": "Assesses and runs optional machine-learning workflows for tabular/remote-sensing GIS tasks. Never invents training data.", "tools": ["ml_capabilities", "ml_prepare_dataset", "ml_train_or_predict", "ml_validate_result"]},
    "internet": {"description": "Searches the public internet for geographic data, finds named boundaries and downloads polygon GeoJSON for direct loading into QGIS. It reports the source used.", "tools": ["internet_search", "internet_find_polygon", "internet_add_polygon"]},
}

def role_dict(name: str):
    return AGENTS[name]
