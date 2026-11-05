"""AI GIS AGENT multi-agent coordinator.

The Coordinator is intentionally deterministic: Copilot/another LLM performs
semantic reasoning while this module supplies stable routing, mission plans,
validation gates, recovery rules and ML escalation hints.
"""
from typing import Any, Dict, List
from .definitions import AGENTS, role_dict

_CARTO = ("map", "layout", "legend", "scale bar", "cartography", "simbolog", "symbology", "style", "qml", "pdf", "png", "svg", "mapa")
_ANALYSIS = ("buffer", "intersect", "intersection", "erase", "difference", "clip", "dissolve", "union", "spatial", "join", "reproject", "distance", "area", "select", "raster", "processing", "geoprocess", "proximity", "overlay")
_VALIDATION = ("validate", "valid", "check", "error", "correct", "fix", "geometry", "crs", "topolog")
_ML = ("machine learning", "machine-learning", "ml", "modelo predictivo", "predict", "clasifica", "classification", "regression", "cluster", "clustering", "random forest", "xgboost", "entrenar", "train", "predicción", "prediction", "teledetección", "remote sensing", "change detection")
_DESTRUCTIVE = ("delete", "remove", "overwrite", "borrar", "eliminar", "sobrescribir", "modify original", "editar original")
_PERSIST = ("save", "guardar", "export", "exportar", "gpkg", "geopackage", "geojson", "shapefile", "pdf", "png", "svg")
_INTERNET = ("internet", "web", "online", "internet", "buscar", "busca", "search", "download", "descarga", "descargar", "openstreetmap", "osm", "polygon", "polígono", "limite", "límite", "boundary", "cataluña", "catalunya")


def _has(text: str, terms) -> bool:
    t = text.lower()
    return any(term in t for term in terms)


def route_task(task: str, context: Dict[str, Any] | None = None) -> Dict[str, Any]:
    context = context or {}
    stages: List[str] = ["analyst", "planner"]
    if _has(task, _ANALYSIS):
        stages.append("geoprocessing")
    if _has(task, _ML):
        stages.append("ml")
    if _has(task, _INTERNET):
        stages.append("internet")
    if _has(task, _CARTO):
        stages.append("cartography")
    # Validator is always a gate, never an optional afterthought.
    stages.append("validator")
    stages = list(dict.fromkeys(stages))
    destructive = _has(task, _DESTRUCTIVE)
    persistence = _has(task, _PERSIST)
    return {
        "task": task,
        "agents": stages,
        "roles": {name: role_dict(name) for name in stages},
        "execution_contract": {
            "inspect_before_assumptions": True,
            "validate_after_major_step": True,
            "metric_operations_require_crs_check": True,
            "intermediate_output": "memory",
            "persistence_requested": persistence,
            "destructive_operation": destructive,
            "confirmation_required": destructive,
            "backup_prompt_before_destructive_edit": True,
            "default_destructive_mode": "ask_user_and_offer_backup",
            "auto_recovery": True,
            "max_recovery_attempts": 2,
            "ml_optional": True,
        },
        "context": context,
        "next_action": "analyst.inspect_project",
    }


def build_plan(task: str, context: Dict[str, Any] | None = None) -> Dict[str, Any]:
    route = route_task(task, context)
    steps = [
        {"id": 1, "agent": "analyst", "action": "inspect_project", "tool": "gis_inspect"},
        {"id": 2, "agent": "analyst", "action": "inspect_inputs", "tool": "gis_inspect_layer"},
        {"id": 3, "agent": "validator", "action": "validate_inputs", "tool": "gis_validate"},
    ]
    n = 4
    if _has(task, _ANALYSIS):
        steps += [
            {"id": n, "agent": "planner", "action": "choose_operation", "tool": "processing_help_or_high_level_tool"},
            {"id": n + 1, "agent": "geoprocessing", "action": "execute_analysis", "tool": "appropriate_GIS_tool", "output": "TEMPORARY_OUTPUT"},
            {"id": n + 2, "agent": "validator", "action": "validate_output", "tool": "gis_validate"},
        ]
        n += 3
    if "internet" in route["agents"]:
        steps += [
            {"id": n, "agent": "internet", "action": "search_external_geodata", "tool": "internet_search_or_internet_find_polygon"},
            {"id": n + 1, "agent": "internet", "action": "download_and_prepare_vector", "tool": "internet_add_polygon"},
            {"id": n + 2, "agent": "validator", "action": "validate_downloaded_layer", "tool": "gis_inspect_layer"},
        ]
        n += 3
    if _has(task, _ML):
        steps += [
            {"id": n, "agent": "ml", "action": "assess_ml_feasibility", "tool": "ml_capabilities"},
            {"id": n + 1, "agent": "ml", "action": "prepare_features_and_target", "tool": "ml_prepare_dataset"},
            {"id": n + 2, "agent": "ml", "action": "train_or_predict", "tool": "ml_train_or_predict"},
            {"id": n + 3, "agent": "validator", "action": "validate_model_result", "tool": "ml_validate_result"},
        ]
        n += 4
    if _has(task, _CARTO):
        steps += [
            {"id": n, "agent": "cartography", "action": "style_and_layout", "tool": "cartography_tools"},
            {"id": n + 1, "agent": "validator", "action": "validate_presentation", "tool": "gis_inspect"},
        ]
        n += 2
    if route["execution_contract"]["persistence_requested"]:
        steps.append({"id": n, "agent": "planner", "action": "persist_if_explicitly_requested", "tool": "save_as_geopackage_or_requested_export"})
    return {
        **route,
        "steps": steps,
        "recovery_policy": {
            "on_validation_failure": ["diagnose", "fix", "re-run_failed_step", "validate_again"],
            "max_attempts": 2,
            "never_overwrite_original_without_confirmation": True,
            "offer_backup_before_destructive_operations": True,
        },
        "persistence_policy": {"intermediate": "memory", "default_vector": "GPKG", "geojson": "explicit_only"},
    }


def build_mission(task: str, context: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Return a complete autonomous mission contract for an LLM host."""
    plan = build_plan(task, context)
    return {
        "mission_id": "ai_gis_agent-mission",
        "status": "ready",
        "goal": task,
        "coordinator": "coordinator",
        "workflow": plan,
        "loop": ["inspect", "plan", "execute", "validate", "recover_if_needed", "present", "persist_if_requested"],
        "handoff_rule": "Each specialist returns structured findings; Coordinator decides the next specialist.",
        "completion_rule": "Do not report success until the final Validator gate passes.",
    }
