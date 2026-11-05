from .aigis_safe_backup import create_project_backup
from pathlib import Path
import json
import os
import tempfile
import shutil
import processing

from qgis.PyQt.QtCore import QVariant
from qgis.PyQt.QtGui import QColor, QFont
from qgis.core import (
    Qgis,
    QgsApplication,
    QgsCoordinateReferenceSystem,
    QgsExpression,
    QgsExpressionContext,
    QgsFeature,
    QgsField,
    QgsGeometry,
    QgsLayout,
    QgsLayoutExporter,
    QgsLayoutItemLabel,
    QgsLayoutItemLegend,
    QgsLayoutItemMap,
    QgsLayoutItemScaleBar,
    QgsProject,
    QgsRasterLayer,
    QgsRectangle,
    QgsSymbol,
    QgsVectorLayer,
    QgsVectorFileWriter,
    QgsWkbTypes,
)


class CommandDispatcher:
    """
    Main-thread QGIS command API for AI GIS AGENT 0.4.

    The MCP layer should use these commands instead of importing QGIS directly.
    """

    def __init__(self, iface):
        self.iface = iface
        self._snapshots = {}
        # Output policy: intermediate results remain inside QGIS memory.
        # Disk files are created only when an explicit output path is supplied.
        self.DEFAULT_OUTPUT_MODE = "memory"
        self.DEFAULT_VECTOR_FORMAT = "GPKG"

    # ---------------- common ----------------

    def layer(self, value):
        project = QgsProject.instance()
        layer = project.mapLayer(str(value))
        if layer:
            return layer
        for candidate in project.mapLayers().values():
            if candidate.name() == str(value):
                return candidate
        raise ValueError(f"Capa no encontrada: {value}")

    def _safety_prompt(self, title, message, snapshot_layer=None):
        """Ask before destructive edits and optionally create a visible project backup."""
        from qgis.PyQt.QtWidgets import QMessageBox
        box = QMessageBox(self.iface.mainWindow() if self.iface else None)
        box.setWindowTitle(title)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setText(message)
        box.setInformativeText(
            "A backup is recommended before continuing. Would you like to create one now?"
        )
        backup_btn = box.addButton("Create backup and continue", QMessageBox.ButtonRole.AcceptRole)
        continue_btn = box.addButton("Continue without backup", QMessageBox.ButtonRole.DestructiveRole)
        cancel_btn = box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(cancel_btn)
        getattr(box, 'exec' if hasattr(box, 'exec') else 'exec' + '_')()
        clicked = box.clickedButton()
        if clicked is cancel_btn:
            raise PermissionError("Operation cancelled by the user.")
        if clicked is backup_btn:
            backup = create_project_backup()
            return {"allowed": True, "backup": backup}
        return {"allowed": True, "backup": None}

    def layer_info(self, layer):
        info = {
            "id": layer.id(),
            "name": layer.name(),
            "type": int(layer.type()),
            "crs": layer.crs().authid(),
            "source": layer.source(),
            "provider": layer.providerType(),
            "valid": layer.isValid(),
            "visible": self._layer_visibility(layer),
            "opacity": layer.opacity(),
        }
        if hasattr(layer, "featureCount"):
            info["feature_count"] = layer.featureCount()
        if hasattr(layer, "extent"):
            e = layer.extent()
            info["extent"] = {
                "xmin": e.xMinimum(), "ymin": e.yMinimum(),
                "xmax": e.xMaximum(), "ymax": e.yMaximum()
            }
        if hasattr(layer, "fields"):
            info["fields"] = [
                {"name": f.name(), "type": f.typeName(),
                 "length": f.length(), "precision": f.precision()}
                for f in layer.fields()
            ]
        return info

    def dispatch(self, command, p):
        handlers = {
            "status": self.status,
            "project_info": self.project_info,
            "list_layers": self.list_layers,
            "get_layer_info": self.get_layer_info,

            "add_vector_layer": self.add_vector_layer,
            "add_raster_layer": self.add_raster_layer,
            "add_wms_layer": self.add_wms_layer,
            "add_xyz_layer": self.add_xyz_layer,
            "remove_layer": self.remove_layer,
            "rename_layer": self.rename_layer,
            "set_visibility": self.set_visibility,
            "set_layer_order": self.set_layer_order,

            "create_memory_layer": self.create_memory_layer,
            "create_geopackage": self.create_geopackage,
            "save_vector_layer": self.save_vector_layer,
            "save_as_geopackage": self.save_as_geopackage,

            "run_processing": self.run_processing,
            "processing_help": self.processing_help,

            "buffer": self.buffer,
            "intersection": self.intersection,
            "difference": self.difference,
            "clip": self.clip,
            "dissolve": self.dissolve,
            "union": self.union,
            "spatial_join": self.spatial_join,
            "reproject": self.reproject,
            "prepare_metric_layer": self.prepare_metric_layer,

            "add_field": self.add_field,
            "calculate_field": self.calculate_field,
            "select_by_attribute": self.select_by_attribute,
            "select_by_location": self.select_by_location,
            "get_features": self.get_features,
            "create_feature": self.create_feature,
            "update_feature": self.update_feature,
            "delete_selected": self.delete_selected,

            "set_single_symbol": self.set_single_symbol,
            "set_categorized_renderer": self.set_categorized_renderer,
            "set_graduated_renderer": self.set_graduated_renderer,
            "load_qml_style": self.load_qml_style,
            "save_qml_style": self.save_qml_style,

            "zoom_to_layer": self.zoom_to_layer,
            "zoom_to_selection": self.zoom_to_selection,
            "get_canvas_extent": self.get_canvas_extent,
            "set_canvas_extent": self.set_canvas_extent,

            "create_layout": self.create_layout,
            "list_layouts": self.list_layouts,
            "delete_layout": self.delete_layout,
            "add_layout_map": self.add_layout_map,
            "add_layout_label": self.add_layout_label,
            "add_layout_legend": self.add_layout_legend,
            "add_layout_scalebar": self.add_layout_scalebar,
            "export_layout": self.export_layout,

            "save_project": self.save_project,

            "snapshot_layer": self.snapshot_layer,
            "rollback_layer": self.rollback_layer,
            "run_workflow": self.run_workflow,
        }
        if command not in handlers:
            raise ValueError(f"Comando desconocido: {command}")
        return handlers[command](p)

    # ---------------- project/layers ----------------

    def status(self, _):
        project = QgsProject.instance()
        return {
            "connected": True,
            "qgis_version": Qgis.version() if "Qgis" in globals() else QgsApplication.applicationVersion(),
            "project": project.fileName() or None,
            "project_title": project.title(),
            "layer_count": len(project.mapLayers()),
            "layout_count": len(project.layoutManager().printLayouts()),
        }

    def project_info(self, _):
        project = QgsProject.instance()
        return {
            "file": project.fileName() or None,
            "title": project.title(),
            "crs": project.crs().authid(),
            "layer_count": len(project.mapLayers()),
            "layers": self.list_layers({}),
            "layouts": self.list_layouts({}),
        }

    def list_layers(self, _):
        return [self.layer_info(layer) for layer in QgsProject.instance().mapLayers().values()]

    def get_layer_info(self, p):
        return self.layer_info(self.layer(p["layer"]))

    def add_vector_layer(self, p):
        layer = QgsVectorLayer(
            p["source"],
            p.get("name") or Path(p["source"].split("|")[0]).stem,
            p.get("provider", "ogr"),
        )
        if not layer.isValid():
            raise ValueError(f"No se pudo cargar la capa vectorial: {p['source']}")
        QgsProject.instance().addMapLayer(layer)
        return self.layer_info(layer)

    def add_raster_layer(self, p):
        layer = QgsRasterLayer(p["source"], p.get("name") or Path(p["source"]).stem)
        if not layer.isValid():
            raise ValueError(f"No se pudo cargar el raster: {p['source']}")
        QgsProject.instance().addMapLayer(layer)
        return self.layer_info(layer)

    def add_wms_layer(self, p):
        uri = p["uri"]
        layer = QgsRasterLayer(uri, p["name"], "wms")
        if not layer.isValid():
            raise ValueError("No se pudo cargar la capa WMS/WMTS")
        QgsProject.instance().addMapLayer(layer)
        return self.layer_info(layer)

    def add_xyz_layer(self, p):
        """Add a reliable XYZ tile basemap and place it at the bottom of the layer tree.

        Accepts either a raw XYZ URL or a built-in provider name. QGIS uses the
        ``wms`` raster provider for XYZ tiles, with ``type=xyz`` in the URI.
        """
        from urllib.parse import quote

        providers = {
            "osm": ("OpenStreetMap", "https://tile.openstreetmap.org/{z}/{x}/{y}.png", 19),
            "openstreetmap": ("OpenStreetMap", "https://tile.openstreetmap.org/{z}/{x}/{y}.png", 19),
            "esri": ("Esri World Imagery", "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", 23),
            "esri_world_imagery": ("Esri World Imagery", "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", 23),
            "carto_positron": ("CartoDB Positron", "https://basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png", 20),
            "cartodb_positron": ("CartoDB Positron", "https://basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png", 20),
            "carto_dark": ("CartoDB Dark Matter", "https://basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png", 20),
            "cartodb_dark": ("CartoDB Dark Matter", "https://basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png", 20),
        }

        raw_uri = str(p.get("uri") or "").strip()
        provider = str(p.get("provider") or "").strip().lower()
        name = str(p.get("name") or "").strip()

        if provider and provider in providers and not raw_uri:
            default_name, raw_uri, default_zmax = providers[provider]
            name = name or default_name
        else:
            default_zmax = int(p.get("zmax") or 19)

        if not raw_uri:
            # OpenStreetMap is the safe default when the agent asks for a generic basemap.
            name = name or "OpenStreetMap"
            raw_uri = providers["osm"][1]
            default_zmax = providers["osm"][2]

        if raw_uri.lower().startswith("type=xyz"):
            uri = raw_uri
        else:
            # QGIS's XYZ URI is parsed as key=value pairs. Any '&' belonging to
            # the remote URL must therefore be percent-encoded so it cannot be
            # mistaken for another provider parameter.
            encoded_url = quote(raw_uri, safe=":/?=%{}")
            uri = f"type=xyz&url={encoded_url}&zmin=0&zmax={default_zmax}"

        name = name or "XYZ Basemap"
        layer = QgsRasterLayer(uri, name, "wms")
        if not layer.isValid():
            provider_error = ""
            try:
                provider_error = layer.dataProvider().lastError() if layer.dataProvider() else ""
            except Exception as exc:
                provider_error = f"Provider diagnostic unavailable: {exc}"
            detail = f" ({provider_error})" if provider_error else ""
            raise ValueError(
                f"No se pudo crear la capa XYZ '{name}'. URL: {raw_uri}{detail}"
            )

        project = QgsProject.instance()
        project.addMapLayer(layer, False)

        # Insert at the bottom of the layer tree so thematic layers remain above it.
        root = project.layerTreeRoot()
        root.insertLayer(-1, layer)

        return self.layer_info(layer)

    def remove_layer(self, p):
        layer = self.layer(p["layer"])
        safety = self._safety_prompt(
            "AI GIS AGENT — Operación destructiva",
            f"Vas a quitar la capa '{layer.name()}' del proyecto QGIS.",
            layer.name(),
        )
        QgsProject.instance().removeMapLayer(layer.id())
        return {"removed": True, "layer": layer.name(), "id": layer.id(), "backup": safety["backup"]}

    def rename_layer(self, p):
        layer = self.layer(p["layer"])
        old = layer.name()
        layer.setName(p["name"])
        return {"old": old, "new": layer.name(), "id": layer.id()}

    def set_visibility(self, p):
        layer = self.layer(p["layer"])
        visible = bool(p.get("visible", True))
        actual = self._set_layer_visibility(layer, visible)
        return {"layer": layer.name(), "visible": actual}

    def set_layer_order(self, p):
        root = QgsProject.instance().layerTreeRoot()
        layer = self.layer(p["layer"])
        node = root.findLayer(layer.id())
        if node is None:
            raise ValueError("No se encontró el nodo de la capa")
        root.removeChildNode(node)
        index = max(0, min(int(p.get("index", 0)), len(root.children())))
        root.insertChildNode(index, node)
        return {"layer": layer.name(), "index": index}

    # ---------------- creation/export ----------------

    def create_memory_layer(self, p):
        geometry = p.get("geometry", "Point")
        crs = p.get("crs", "EPSG:4326")
        uri = f"{geometry}?crs={crs}"
        layer = QgsVectorLayer(uri, p["name"], "memory")
        if not layer.isValid():
            raise ValueError("No se pudo crear la capa temporal")
        for field in p.get("fields", []):
            qtype = {
                "string": QVariant.String,
                "integer": QVariant.Int,
                "double": QVariant.Double,
                "date": QVariant.Date,
            }.get(field.get("type", "string"), QVariant.String)
            layer.dataProvider().addAttributes([
                QgsField(field["name"], qtype, len=field.get("length", 0),
                         prec=field.get("precision", 0))
            ])
        layer.updateFields()
        QgsProject.instance().addMapLayer(layer)
        return self.layer_info(layer)

    def create_geopackage(self, p):
        path = str(p["path"])
        name = p["name"]
        geometry = p.get("geometry", "Polygon")
        crs = p.get("crs", "EPSG:4326")

        if not path.lower().endswith(".gpkg"):
            path += ".gpkg"

        # Ensure the target directory exists.
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)

        uri = f"{geometry}?crs={crs}"
        layer = QgsVectorLayer(uri, name, "memory")
        if not layer.isValid():
            raise ValueError("No se pudo crear la capa base")

        for field in p.get("fields", []):
            qtype = {
                "string": QVariant.String,
                "integer": QVariant.Int,
                "double": QVariant.Double,
                "date": QVariant.Date,
                "bool": QVariant.Bool,
            }.get(field.get("type", "string"), QVariant.String)
            layer.dataProvider().addAttributes([QgsField(field["name"], qtype)])
        layer.updateFields()

        options = QgsVectorFileWriter.SaveVectorOptions()
        options.driverName = "GPKG"
        options.layerName = name
        options.actionOnExistingFile = QgsVectorFileWriter.ActionOnExistingFile.CreateOrOverwriteFile

        result = QgsVectorFileWriter.writeAsVectorFormatV3(
            layer, path, QgsProject.instance().transformContext(), options
        )
        error_code = result[0]
        error_message = result[1] if len(result) > 1 else ""

        if error_code != QgsVectorFileWriter.WriterError.NoError:
            raise RuntimeError(
                f"No se pudo crear el GeoPackage '{path}': "
                f"{error_message or error_code}"
            )

        # Load the persistent layer back into the project.
        saved = QgsVectorLayer(f"{path}|layername={name}", name, "ogr")
        if not saved.isValid():
            raise RuntimeError(
                f"El GeoPackage se creó pero QGIS no pudo abrir la capa '{name}' desde '{path}'."
            )
        QgsProject.instance().addMapLayer(saved)
        return self.layer_info(saved)


    def save_vector_layer(self, p):
        layer = self.layer(p["layer"])
        path = str(p["path"])

        # If the user asks for persistence without a format, use GeoPackage.
        if not Path(path).suffix:
            path += ".gpkg"

        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)

        options = QgsVectorFileWriter.SaveVectorOptions()
        options.driverName = "GPKG" if path.lower().endswith(".gpkg") else ""
        options.layerName = p.get("layer_name") or layer.name()
        options.actionOnExistingFile = QgsVectorFileWriter.ActionOnExistingFile.CreateOrOverwriteFile

        if options.driverName == "GPKG":
            options.layerName = p.get("layer_name") or layer.name()

        result = QgsVectorFileWriter.writeAsVectorFormatV3(
            layer, path, QgsProject.instance().transformContext(), options
        )
        error_code = result[0]
        error_message = result[1] if len(result) > 1 else ""

        if error_code != QgsVectorFileWriter.WriterError.NoError:
            raise RuntimeError(
                f"No se pudo guardar la capa en '{path}': "
                f"{error_message or error_code}"
            )

        return {
            "saved": True,
            "path": path,
            "layer": layer.name(),
            "format": "GeoPackage" if path.lower().endswith(".gpkg") else "vector"
        }


    # ---------------- layer tree helpers ----------------

    def _layer_tree_node(self, layer):
        """Return the QgsLayerTreeLayer node for a layer, if it exists."""
        root = QgsProject.instance().layerTreeRoot()
        return root.findLayer(layer.id())

    def _layer_visibility(self, layer):
        """Read visibility from the QgsLayerTreeLayer node."""
        node = self._layer_tree_node(layer)
        return bool(node.isVisible()) if node is not None else True

    def _set_layer_visibility(self, layer, visible):
        """Set visibility through QgsLayerTreeLayer."""
        node = self._layer_tree_node(layer)
        if node is None:
            raise RuntimeError(f"Layer '{layer.name()}' is not present in the QGIS layer tree.")
        node.setItemVisibilityChecked(bool(visible))
        return bool(node.isVisible())

    # ---------------- output policy ----------------

    def _output(self, p, key="output"):
        """Return an explicit path, otherwise keep the result in QGIS memory."""
        value = p.get(key)
        if value in (None, "", "TEMPORARY_OUTPUT"):
            return "memory:"
        return value

    def save_as_geopackage(self, p):
        """Persist a layer explicitly as GeoPackage using the QGIS writer API."""
        layer = self.layer(p["layer"])
        path = str(p["path"])
        if not path.lower().endswith(".gpkg"):
            path += ".gpkg"

        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)

        layer_name = p.get("layer_name") or layer.name()

        options = QgsVectorFileWriter.SaveVectorOptions()
        options.driverName = "GPKG"
        options.layerName = layer_name
        options.actionOnExistingFile = QgsVectorFileWriter.ActionOnExistingFile.CreateOrOverwriteFile

        result = QgsVectorFileWriter.writeAsVectorFormatV3(
            layer, path, QgsProject.instance().transformContext(), options
        )
        error_code = result[0]
        error_message = result[1] if len(result) > 1 else ""

        if error_code != QgsVectorFileWriter.WriterError.NoError:
            raise RuntimeError(
                f"No se pudo guardar el GeoPackage '{path}': "
                f"{error_message or error_code}"
            )

        return {
            "saved": True,
            "format": "GPKG",
            "path": path,
            "layer_name": layer_name
        }


    # ---------------- processing ----------------

    def _normalise_result(self, result):
        output = {}
        for key, value in result.items():
            if isinstance(value, (QgsVectorLayer, QgsRasterLayer)):
                if value.isValid() and QgsProject.instance().mapLayer(value.id()) is None:
                    QgsProject.instance().addMapLayer(value)
                output[key] = self.layer_info(value)
            else:
                output[key] = value
        return output

    def run_processing(self, p):
        algorithm = p["algorithm"]
        params = dict(p.get("parameters") or {})

        # Never silently create a disk file for an intermediate result.
        # If OUTPUT is omitted, inspect the algorithm and inject memory:.
        if "OUTPUT" in params and params["OUTPUT"] in (None, "", "TEMPORARY_OUTPUT"):
            params["OUTPUT"] = "memory:"
        elif "OUTPUT" not in params:
            alg = QgsApplication.processingRegistry().algorithmById(algorithm)
            if alg:
                for definition in alg.parameterDefinitions():
                    if definition.name().upper() == "OUTPUT":
                        params["OUTPUT"] = "memory:"
                        break

        result = processing.run(algorithm, params)
        return {
            "algorithm": algorithm,
            "output_mode": "memory" if params.get("OUTPUT") == "memory:" else "persistent",
            "results": self._normalise_result(result)
        }

    def processing_help(self, p):
        alg = QgsApplication.processingRegistry().algorithmById(p["algorithm"])
        if alg is None:
            raise ValueError(f"Algoritmo no encontrado: {p['algorithm']}")
        return {
            "id": alg.id(),
            "name": alg.displayName(),
            "group": alg.group(),
            "provider": alg.provider().id() if alg.provider() else None,
            "parameters": [
                {
                    "name": d.name(),
                    "description": d.description(),
                    "type": d.type(),
                    "default": str(d.defaultValue()),
                    "flags": int(d.flags()),
                }
                for d in alg.parameterDefinitions()
            ],
        }

    def proc(self, algorithm, params):
        return self.run_processing({"algorithm": algorithm, "parameters": params})

    def buffer(self, p):
        return self.proc("native:buffer", {
            "INPUT": self.layer(p["layer"]),
            "DISTANCE": p["distance"],
            "SEGMENTS": p.get("segments", 5),
            "DISSOLVE": p.get("dissolve", False),
            "OUTPUT": self._output(p, "output"),
        })

    def intersection(self, p):
        return self.proc("native:intersection", {
            "INPUT": self.layer(p["input"]),
            "OVERLAY": self.layer(p["overlay"]),
            "OUTPUT": self._output(p, "output"),
        })

    def difference(self, p):
        return self.proc("native:difference", {
            "INPUT": self.layer(p["input"]),
            "OVERLAY": self.layer(p["overlay"]),
            "OUTPUT": self._output(p, "output"),
        })

    def clip(self, p):
        return self.proc("native:clip", {
            "INPUT": self.layer(p["input"]),
            "OVERLAY": self.layer(p["overlay"]),
            "OUTPUT": self._output(p, "output"),
        })

    def dissolve(self, p):
        return self.proc("native:dissolve", {
            "INPUT": self.layer(p["layer"]),
            "FIELD": p.get("fields", []),
            "OUTPUT": self._output(p, "output"),
        })

    def union(self, p):
        return self.proc("native:union", {
            "INPUT": self.layer(p["input"]),
            "OVERLAY": self.layer(p["overlay"]),
            "OUTPUT": self._output(p, "output"),
        })

    def spatial_join(self, p):
        return self.proc("native:joinattributesbylocation", {
            "INPUT": self.layer(p["input"]),
            "JOIN": self.layer(p["join"]),
            "PREDICATE": p.get("predicate", [0]),
            "JOIN_FIELDS": p.get("join_fields", []),
            "METHOD": p.get("method", 0),
            "DISCARD_NONMATCHING": p.get("discard_nonmatching", False),
            "PREFIX": p.get("prefix", ""),
            "OUTPUT": self._output(p, "output"),
        })

    def reproject(self, p):
        return self.proc("native:reprojectlayer", {
            "INPUT": self.layer(p["layer"]),
            "TARGET_CRS": p["crs"],
            "OUTPUT": self._output(p, "output"),
        })

    def prepare_metric_layer(self, p):
        """Return a projected layer suitable for distance/area operations.

        Geographic layers are projected to a local UTM zone derived from the
        layer extent. Already-projected layers are returned unchanged.
        """
        layer = self.layer(p["layer"])
        if not isinstance(layer, QgsVectorLayer):
            raise ValueError("Las operaciones métricas requieren una capa vectorial")
        crs = layer.crs()
        if not crs.isValid():
            raise ValueError("La capa no tiene un CRS válido")
        if not crs.isGeographic():
            return {
                "prepared": False,
                "reason": "already_projected",
                "layer": self.layer_info(layer),
                "crs": crs.authid(),
            }

        extent = layer.extent()
        if extent.isEmpty():
            raise ValueError("No se puede elegir un CRS métrico para una capa sin extensión")
        lon = (extent.xMinimum() + extent.xMaximum()) / 2.0
        lat = (extent.yMinimum() + extent.yMaximum()) / 2.0
        if lon < -180 or lon > 180 or lat < -90 or lat > 90:
            raise ValueError("La extensión geográfica no parece estar en grados válidos")
        zone = int((lon + 180) / 6) + 1
        zone = max(1, min(zone, 60))
        epsg = 32600 + zone if lat >= 0 else 32700 + zone
        target = QgsCoordinateReferenceSystem(f"EPSG:{epsg}")
        result = self.proc("native:reprojectlayer", {
            "INPUT": layer,
            "TARGET_CRS": target,
            "OUTPUT": self._output(p, "output"),
        })
        result["metric_crs_selection"] = {
            "method": "UTM_from_layer_centroid",
            "source_crs": crs.authid(),
            "target_crs": target.authid(),
            "zone": zone,
            "hemisphere": "north" if lat >= 0 else "south",
            "longitude": lon,
            "latitude": lat,
        }
        return result

    # ---------------- features ----------------

    def add_field(self, p):
        layer = self.layer(p["layer"])
        if not isinstance(layer, QgsVectorLayer):
            raise ValueError("Se necesita una capa vectorial")
        qtype = {
            "string": QVariant.String,
            "integer": QVariant.Int,
            "double": QVariant.Double,
            "date": QVariant.Date,
        }.get(p.get("type", "string"), QVariant.String)
        if p["field"] in layer.fields().names():
            raise ValueError(f"El campo ya existe: {p['field']}")
        layer.dataProvider().addAttributes([
            QgsField(p["field"], qtype, len=p.get("length", 0),
                     prec=p.get("precision", 0))
        ])
        layer.updateFields()
        return {"added": True, "field": p["field"]}

    def calculate_field(self, p):
        layer = self.layer(p["layer"])
        if not isinstance(layer, QgsVectorLayer):
            raise ValueError("calculate_field requiere vectorial")
        index = layer.fields().indexOf(p["field"])
        if index < 0:
            self.add_field({
                "layer": p["layer"], "field": p["field"],
                "type": p.get("field_type", "double")
            })
            index = layer.fields().indexOf(p["field"])

        expression = QgsExpression(p["expression"])
        if expression.hasParserError():
            raise ValueError(expression.parserErrorString())

        if not layer.startEditing():
            raise RuntimeError("No se pudo iniciar edición")
        context = QgsExpressionContext()
        updated = 0
        for f in layer.getFeatures():
            context.setFeature(f)
            value = expression.evaluate(context)
            if expression.hasEvalError():
                layer.rollBack()
                raise ValueError(expression.evalErrorString())
            layer.changeAttributeValue(f.id(), index, value)
            updated += 1
        if not layer.commitChanges():
            raise RuntimeError("No se pudieron guardar cambios")
        return {"updated": updated, "field": p["field"]}

    def select_by_attribute(self, p):
        layer = self.layer(p["layer"])
        layer.selectByExpression(p["expression"])
        return {"selected": layer.selectedFeatureCount()}

    def select_by_location(self, p):
        return self.proc("native:selectbylocation", {
            "INPUT": self.layer(p["input"]),
            "PREDICATE": p.get("predicate", [0]),
            "INTERSECT": self.layer(p["intersect"]),
            "METHOD": p.get("method", 0),
        })

    def get_features(self, p):
        layer = self.layer(p["layer"])
        limit = min(max(int(p.get("limit", 100)), 1), 10000)
        request = layer.getFeatures()
        if p.get("filter_expression"):
            from qgis.core import QgsFeatureRequest
            request = layer.getFeatures(
                QgsFeatureRequest().setFilterExpression(p["filter_expression"])
            )
        result = []
        for f in request:
            item = {
                "id": f.id(),
                "attributes": dict(zip(layer.fields().names(), f.attributes()))
            }
            if p.get("include_geometry"):
                item["geometry_wkt"] = f.geometry().asWkt()
            result.append(item)
            if len(result) >= limit:
                break
        return {"count": len(result), "features": result}

    def create_feature(self, p):
        layer = self.layer(p["layer"])
        if not isinstance(layer, QgsVectorLayer):
            raise ValueError("Se necesita capa vectorial")
        feature = QgsFeature(layer.fields())
        attrs = p.get("attributes", {})
        for name, value in attrs.items():
            if layer.fields().indexOf(name) >= 0:
                feature[name] = value
        if p.get("geometry_wkt"):
            feature.setGeometry(QgsGeometry.fromWkt(p["geometry_wkt"]))

        if not layer.startEditing():
            raise RuntimeError("No se pudo iniciar edición")
        if not layer.addFeature(feature):
            layer.rollBack()
            raise RuntimeError("No se pudo crear la entidad")
        if not layer.commitChanges():
            raise RuntimeError("No se pudieron guardar cambios")
        return {"created": True, "feature_id": feature.id()}

    def update_feature(self, p):
        layer = self.layer(p["layer"])
        fid = int(p["feature_id"])
        if not p.get("confirm"):
            raise PermissionError(
                "Modificar una entidad requiere confirm=true para activar la confirmación y backup."
            )
        safety = self._safety_prompt(
            "AI GIS AGENT — Modificación de datos",
            f"Vas a modificar la entidad {fid} de la capa '{layer.name()}'.",
            layer.name(),
        )
        if not layer.startEditing():
            raise RuntimeError("No se pudo iniciar edición")
        if p.get("attributes"):
            for name, value in p["attributes"].items():
                idx = layer.fields().indexOf(name)
                if idx >= 0:
                    layer.changeAttributeValue(fid, idx, value)
        if p.get("geometry_wkt"):
            layer.changeGeometry(fid, QgsGeometry.fromWkt(p["geometry_wkt"]))
        if not layer.commitChanges():
            raise RuntimeError("No se pudieron guardar cambios")
        return {"updated": True, "feature_id": fid}

    def delete_selected(self, p):
        layer = self.layer(p["layer"])
        count = layer.selectedFeatureCount()
        if not p.get("confirm"):
            raise PermissionError(
                f"Operación destructiva: se eliminarían {count} entidades. "
                "Repite con confirm=true."
            )
        safety = self._safety_prompt(
            "AI GIS AGENT — Operación destructiva",
            f"Vas a eliminar {count} entidades seleccionadas de '{layer.name()}'.",
            layer.name(),
        )
        if not layer.startEditing():
            raise RuntimeError("No se pudo iniciar edición")
        if not layer.deleteSelectedFeatures():
            layer.rollBack()
            raise RuntimeError("No se pudieron eliminar entidades")
        if not layer.commitChanges():
            raise RuntimeError("No se pudieron guardar cambios")
        return {"deleted": count, "backup": safety["backup"]}

    # ---------------- symbology ----------------

    def set_single_symbol(self, p):
        layer = self.layer(p["layer"])
        if not isinstance(layer, QgsVectorLayer):
            raise ValueError("La simbología requiere vectorial")

        symbol = QgsSymbol.defaultSymbol(layer.geometryType())
        color = p.get("color")
        if color:
            symbol.setColor(QColor(color))
        if p.get("size") is not None:
            symbol.setSize(float(p["size"]))
        if p.get("opacity") is not None:
            symbol.setOpacity(float(p["opacity"]))

        layer.setRenderer(__import__("qgis").core.QgsSingleSymbolRenderer(symbol))
        layer.triggerRepaint()
        return {"styled": True, "renderer": "single"}

    def set_categorized_renderer(self, p):
        layer = self.layer(p["layer"])
        if not isinstance(layer, QgsVectorLayer):
            raise ValueError("La simbología requiere vectorial")

        field = p["field"]
        categories = []
        base = QgsSymbol.defaultSymbol(layer.geometryType())

        from qgis.core import QgsRendererCategory, QgsCategorizedSymbolRenderer
        for item in p.get("categories", []):
            symbol = base.clone()
            if item.get("color"):
                symbol.setColor(QColor(item["color"]))
            if item.get("size") is not None:
                symbol.setSize(float(item["size"]))
            categories.append(
                QgsRendererCategory(item["value"], symbol, item.get("label", str(item["value"])))
            )

        layer.setRenderer(QgsCategorizedSymbolRenderer(field, categories))
        layer.triggerRepaint()
        return {"styled": True, "renderer": "categorized", "field": field}

    def set_graduated_renderer(self, p):
        layer = self.layer(p["layer"])
        if not isinstance(layer, QgsVectorLayer):
            raise ValueError("La simbología requiere vectorial")

        from qgis.core import QgsGraduatedSymbolRenderer, QgsClassificationJenks
        renderer = QgsGraduatedSymbolRenderer(p["field"])
        renderer.setClassAttribute(p["field"])
        renderer.setClassificationMethod(QgsClassificationJenks())
        renderer.updateClasses(layer, int(p.get("classes", 5)))
        layer.setRenderer(renderer)
        layer.triggerRepaint()
        return {"styled": True, "renderer": "graduated", "field": p["field"]}

    def load_qml_style(self, p):
        layer = self.layer(p["layer"])
        ok, error = layer.loadNamedStyle(p["path"])
        if not ok:
            raise RuntimeError(error or "No se pudo cargar el estilo QML")
        layer.triggerRepaint()
        return {"loaded": True, "path": p["path"]}

    def save_qml_style(self, p):
        layer = self.layer(p["layer"])
        result = layer.saveNamedStyle(p["path"])
        return {"saved": bool(result[0]), "path": p["path"]}

    # ---------------- canvas ----------------

    def zoom_to_layer(self, p):
        layer = self.layer(p["layer"])
        self.iface.mapCanvas().setExtent(layer.extent())
        self.iface.mapCanvas().refresh()
        return {"zoomed": True}

    def zoom_to_selection(self, p):
        layer = self.layer(p["layer"])
        if layer.selectedFeatureCount() == 0:
            raise ValueError("No hay entidades seleccionadas")
        self.iface.mapCanvas().setExtent(layer.boundingBoxOfSelected())
        self.iface.mapCanvas().refresh()
        return {"zoomed": True, "selected": layer.selectedFeatureCount()}

    def get_canvas_extent(self, _):
        e = self.iface.mapCanvas().extent()
        return {
            "xmin": e.xMinimum(), "ymin": e.yMinimum(),
            "xmax": e.xMaximum(), "ymax": e.yMaximum(),
            "crs": self.iface.mapCanvas().mapSettings().destinationCrs().authid()
        }

    def set_canvas_extent(self, p):
        self.iface.mapCanvas().setExtent(QgsRectangle(
            float(p["xmin"]), float(p["ymin"]),
            float(p["xmax"]), float(p["ymax"])
        ))
        self.iface.mapCanvas().refresh()
        return self.get_canvas_extent({})

    # ---------------- layouts ----------------

    def layout(self, name):
        layout = QgsProject.instance().layoutManager().layoutByName(name)
        if layout is None:
            raise ValueError(f"Layout no encontrado: {name}")
        return layout

    def create_layout(self, p):
        manager = QgsProject.instance().layoutManager()
        if manager.layoutByName(p["name"]):
            raise ValueError("El layout ya existe")
        layout = QgsLayout(QgsProject.instance())
        layout.initializeDefaults()
        layout.setName(p["name"])
        manager.addLayout(layout)
        return {"created": True, "name": p["name"]}

    def list_layouts(self, _):
        return [
            {"name": x.name(), "item_count": len(x.items())}
            for x in QgsProject.instance().layoutManager().printLayouts()
        ]

    def delete_layout(self, p):
        manager = QgsProject.instance().layoutManager()
        layout = self.layout(p["name"])
        manager.removeLayout(layout)
        return {"deleted": True}

    def add_layout_map(self, p):
        layout = self.layout(p["layout"])
        item = QgsLayoutItemMap(layout)
        if p.get("extent_from_layer"):
            item.setExtent(self.layer(p["extent_from_layer"]).extent())
        elif p.get("extent"):
            e = p["extent"]
            item.setExtent(QgsRectangle(e["xmin"], e["ymin"], e["xmax"], e["ymax"]))
        layout.addLayoutItem(item)
        item.attemptMove(__import__("qgis").core.QgsLayoutPoint(p.get("x", 10), p.get("y", 10)))
        item.attemptResize(__import__("qgis").core.QgsLayoutSize(p.get("width", 180), p.get("height", 120)))
        item.setFrameEnabled(bool(p.get("frame", True)))
        return {"added": True, "id": item.uuid()}

    def add_layout_label(self, p):
        layout = self.layout(p["layout"])
        item = QgsLayoutItemLabel(layout)
        item.setText(p.get("text", ""))
        item.setFont(QFont(p.get("font_family", "Arial"), int(p.get("font_size", 16))))
        layout.addLayoutItem(item)
        item.attemptMove(__import__("qgis").core.QgsLayoutPoint(p.get("x", 10), p.get("y", 10)))
        item.attemptResize(__import__("qgis").core.QgsLayoutSize(p.get("width", 100), p.get("height", 20)))
        return {"added": True, "id": item.uuid()}

    def add_layout_legend(self, p):
        layout = self.layout(p["layout"])
        item = QgsLayoutItemLegend(layout)
        item.setTitle(p.get("title", "Leyenda"))
        if p.get("map_item_id"):
            m = layout.itemByUuid(p["map_item_id"])
            if m:
                item.setLinkedMap(m)
        layout.addLayoutItem(item)
        item.attemptMove(__import__("qgis").core.QgsLayoutPoint(p.get("x", 195), p.get("y", 10)))
        item.attemptResize(__import__("qgis").core.QgsLayoutSize(p.get("width", 60), p.get("height", 80)))
        return {"added": True, "id": item.uuid()}

    def add_layout_scalebar(self, p):
        layout = self.layout(p["layout"])
        item = QgsLayoutItemScaleBar(layout)
        if p.get("map_item_id"):
            m = layout.itemByUuid(p["map_item_id"])
            if m:
                item.setLinkedMap(m)
        layout.addLayoutItem(item)
        item.attemptMove(__import__("qgis").core.QgsLayoutPoint(p.get("x", 10), p.get("y", 135)))
        item.attemptResize(__import__("qgis").core.QgsLayoutSize(p.get("width", 80), p.get("height", 15)))
        return {"added": True, "id": item.uuid()}

    def export_layout(self, p):
        layout = self.layout(p["layout"])
        output = p["output"]
        ext = Path(output).suffix.lower()
        exporter = QgsLayoutExporter(layout)
        if ext == ".pdf":
            result = exporter.exportToPdf(output, QgsLayoutExporter.PdfExportSettings())
        elif ext == ".svg":
            result = exporter.exportToSvg(output, QgsLayoutExporter.SvgExportSettings())
        elif ext in (".png", ".jpg", ".jpeg"):
            result = exporter.exportToImage(output, QgsLayoutExporter.ImageExportSettings())
        else:
            raise ValueError("Formato de layout no soportado")
        if result != QgsLayoutExporter.ExportResult.Success:
            raise RuntimeError(f"Error exportando layout: {result}")
        return {"exported": True, "path": output}

    def save_project(self, p):
        project = QgsProject.instance()
        ok = project.write(p["path"]) if p.get("path") else project.write()
        return {"saved": bool(ok), "path": project.fileName() or None}

    # ---------------- lightweight snapshots / workflows ----------------

    def snapshot_layer(self, p):
        layer = self.layer(p["layer"])
        # Save a temporary copy; intended for rollback of destructive operations.
        fd, path = tempfile.mkstemp(suffix=".gpkg", prefix="ai_gis_agent_snapshot_")
        os.close(fd)
        result = processing.run("native:savefeatures", {
            "INPUT": layer,
            "OUTPUT": path
        })
        key = p.get("snapshot_id") or layer.id()
        self._snapshots[key] = {"path": path, "layer_name": layer.name()}
        return {"snapshot_id": key, "path": path}

    def rollback_layer(self, p):
        key = p["snapshot_id"]
        snap = self._snapshots.get(key)
        if not snap:
            raise ValueError("Snapshot no encontrado")
        original = self.layer(p["layer"])
        restored = QgsVectorLayer(snap["path"], original.name(), "ogr")
        if not restored.isValid():
            raise RuntimeError("No se pudo abrir el snapshot")
        QgsProject.instance().removeMapLayer(original.id())
        QgsProject.instance().addMapLayer(restored)
        return self.layer_info(restored)

    def run_workflow(self, p):
        """
        Sequential workflow executor.
        Each step is {command: "...", params: {...}}.
        Results are returned in order.
        """
        results = []
        for index, step in enumerate(p.get("steps", [])):
            if not step.get("command"):
                raise ValueError(f"Workflow: falta command en paso {index}")
            result = self.dispatch(step["command"], step.get("params") or {})
            results.append({"step": index, "command": step["command"], "result": result})
        return {"steps": results}


    # ---------------- AI GIS AGENT 0.5 agent helpers ----------------

    def agent_project_snapshot(self):
        """Return structured project state for the planner."""
        project = QgsProject.instance()
        layers = []
        for lyr in project.mapLayers().values():
            layers.append({
                "id": lyr.id(),
                "name": lyr.name(),
                "type": lyr.type(),
                "geometry": QgsWkbTypes.displayString(lyr.wkbType()) if hasattr(lyr, "wkbType") else None,
                "crs": lyr.crs().authid() if lyr.crs().isValid() else None,
                "feature_count": lyr.featureCount() if hasattr(lyr, "featureCount") else None,
            })
        return {
            "project_crs": project.crs().authid() if project.crs().isValid() else None,
            "layers": layers,
        }

    def agent_validate_layer(self, layer):
        """Internal validation used by future autonomous workflows."""
        if layer is None or not layer.isValid():
            return {"ok": False, "reason": "invalid_layer"}
        invalid = 0
        empty = 0
        if hasattr(layer, "getFeatures"):
            for feat in layer.getFeatures():
                geom = feat.geometry()
                if geom is None or geom.isNull() or geom.isEmpty():
                    empty += 1
                else:
                    try:
                        if not geom.isGeosValid():
                            invalid += 1
                    except Exception:
                        # If QGIS cannot evaluate GEOS validity, treat the geometry as invalid
                        # rather than silently accepting an unchecked feature.
                        invalid += 1
        return {
            "ok": invalid == 0 and empty == 0 and layer.crs().isValid(),
            "invalid_geometry_count": invalid,
            "empty_geometry_count": empty,
            "crs": layer.crs().authid() if layer.crs().isValid() else None,
            "feature_count": layer.featureCount() if hasattr(layer, "featureCount") else None,
        }
