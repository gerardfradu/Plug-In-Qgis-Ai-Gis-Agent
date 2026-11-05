"""Optional tabular ML engine for AI GIS AGENT.

Heavy ML dependencies are optional so ordinary QGIS/MCP use is unchanged.
Supported first-line models are Random Forest classification/regression.
Spatial prediction should be treated carefully: train/test splits do not remove
spatial autocorrelation, so the Validator reports this limitation explicitly.
"""
from __future__ import annotations
import os
from typing import Any


def capabilities() -> dict:
    try:
        import sklearn  # noqa: F401
        sklearn_available = True
        version = sklearn.__version__
    except Exception:
        sklearn_available = False
        version = None
    try:
        import pandas  # noqa: F401
        pandas_available = True
    except Exception:
        pandas_available = False
    return {
        "available": sklearn_available and pandas_available,
        "scikit_learn": sklearn_available,
        "scikit_learn_version": version,
        "pandas": pandas_available,
        "models": ["RandomForestClassifier", "RandomForestRegressor"] if sklearn_available else [],
        "note": "ML is optional. Install scikit-learn and pandas in the MCP environment to enable execution.",
    }


def _imports():
    try:
        import pandas as pd
        from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
        from sklearn.metrics import accuracy_score, f1_score, mean_absolute_error, mean_squared_error, r2_score
        from sklearn.model_selection import train_test_split
        return pd, RandomForestClassifier, RandomForestRegressor, accuracy_score, f1_score, mean_absolute_error, mean_squared_error, r2_score, train_test_split
    except ImportError as exc:
        raise RuntimeError("ML requiere 'pandas' y 'scikit-learn' en el entorno del MCP. La funcionalidad GIS normal no depende de ellos.") from exc


def prepare_dataset(features: list[dict], feature_fields: list[str], target_field: str | None = None) -> dict:
    pd, *_ = _imports()
    rows = []
    for f in features:
        attrs = f.get("attributes", f)
        row = {k: attrs.get(k) for k in feature_fields}
        if target_field:
            row[target_field] = attrs.get(target_field)
        row["__fid"] = f.get("id", attrs.get("id"))
        rows.append(row)
    df = pd.DataFrame(rows)
    before = len(df)
    required = feature_fields + ([target_field] if target_field else [])
    df = df.dropna(subset=required)
    return {
        "rows": len(df),
        "rows_dropped_missing": before - len(df),
        "feature_fields": feature_fields,
        "target_field": target_field,
        "dtypes": {c: str(df[c].dtype) for c in df.columns},
        "target_classes": sorted(df[target_field].astype(str).unique().tolist()) if target_field and target_field in df else [],
        "records": df.to_dict(orient="records"),
    }


def train_or_predict(features: list[dict], feature_fields: list[str], target_field: str | None = None,
                     task: str = "classification", model_path: str | None = None,
                     n_estimators: int = 200, random_state: int = 42) -> dict:
    pd, RFC, RFR, accuracy_score, f1_score, mae, mse, r2, train_test_split = _imports()
    from joblib import dump, load
    rows = []
    for f in features:
        attrs = f.get("attributes", f)
        row = {k: attrs.get(k) for k in feature_fields}
        if target_field:
            row[target_field] = attrs.get(target_field)
        row["__fid"] = f.get("id", attrs.get("id"))
        rows.append(row)
    df = pd.DataFrame(rows).dropna(subset=feature_fields + ([target_field] if target_field else []))
    if len(df) < 10:
        raise ValueError("Se necesitan al menos 10 registros completos para un modelo inicial.")
    X = pd.get_dummies(df[feature_fields], dummy_na=True)
    if model_path and os.path.exists(model_path) and not target_field:
        bundle = load(model_path)
        model = bundle["model"]
        columns = bundle["columns"]
        X = X.reindex(columns=columns, fill_value=0)
        pred = model.predict(X)
        return {"mode": "predict", "predictions": [{"fid": fid, "prediction": p.item() if hasattr(p, "item") else p} for fid, p in zip(df["__fid"], pred)], "model_path": model_path}
    if not target_field:
        raise ValueError("Para entrenar debes indicar target_field; para predecir debes indicar un model_path existente.")
    y = df[target_field]
    if task == "classification":
        model = RFC(n_estimators=n_estimators, random_state=random_state, n_jobs=-1, class_weight="balanced")
        stratify = y if y.nunique() > 1 else None
    elif task == "regression":
        model = RFR(n_estimators=n_estimators, random_state=random_state, n_jobs=-1)
        stratify = None
    else:
        raise ValueError("task debe ser 'classification' o 'regression'.")
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.25, random_state=random_state, stratify=stratify)
    model.fit(X_train, y_train)
    pred = model.predict(X_test)
    metrics: dict[str, Any] = {"n": len(df), "test_n": len(X_test), "task": task}
    if task == "classification":
        metrics.update({"accuracy": float(accuracy_score(y_test, pred)), "f1_weighted": float(f1_score(y_test, pred, average="weighted"))})
    else:
        metrics.update({"mae": float(mae(y_test, pred)), "rmse": float(mse(y_test, pred) ** 0.5), "r2": float(r2(y_test, pred))})
    importances = getattr(model, "feature_importances_", None)
    top_features = []
    if importances is not None:
        pairs = sorted(zip(X.columns, importances), key=lambda x: x[1], reverse=True)[:20]
        top_features = [{"feature": str(k), "importance": float(v)} for k, v in pairs]
    if model_path:
        os.makedirs(os.path.dirname(os.path.abspath(model_path)), exist_ok=True)
        dump({"model": model, "columns": list(X.columns), "task": task, "feature_fields": feature_fields}, model_path)
    return {"mode": "train", "metrics": metrics, "top_features": top_features, "model_path": model_path, "spatial_validation_warning": "Random train/test split may overestimate performance when nearby features are spatially autocorrelated."}


def validate_result(result: dict, task: str = "classification") -> dict:
    metrics = result.get("metrics", result)
    warnings = []
    passed = True
    if task == "classification":
        if metrics.get("accuracy", 0) < 0.60:
            passed = False; warnings.append("Accuracy inferior al 0.60.")
        if metrics.get("f1_weighted", 0) < 0.60:
            passed = False; warnings.append("F1 ponderado inferior al 0.60.")
    else:
        if metrics.get("r2", -999) < 0:
            passed = False; warnings.append("R² negativo en el conjunto de prueba.")
    warnings.append("Validación espacial independiente no realizada: considera un split espacial o validación por bloques.")
    return {"passed": passed, "warnings": warnings, "metrics": metrics}
