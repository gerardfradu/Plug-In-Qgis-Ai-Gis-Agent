# AI GIS Agent

Plugin de QGIS y servidor MCP para integrar inteligencia artificial, orquestación de agentes y aprendizaje automático (ML) en tareas de análisis espacial y cartografía.

## ¿Qué hace?

* **Integración MCP (Model Context Protocol):** Conecta QGIS con servidores de lenguaje y herramientas de IA (`mcp_server/qgis_mcp_server.py`).
* **Agentes especializados (`agents/`):** Incluye roles dedicados para geoprocesamiento, validación de datos, análisis de datos, planificación y diseño cartográfico.
* **Motor de Machine Learning (`ml_engine.py`):** Soporte para tareas avanzadas de clasificación y análisis espacial con ML directamente sobre datos GIS.
* **Puente con QGIS (`bridge.py` & `plugin.py`):** Permite ejecutar comandos y scripts directamente desde la interfaz de QGIS.

## Estructura del repositorio

* `plugin.py`: Punto de entrada del complemento en la interfaz de QGIS.
* `bridge.py`: Gestor de comunicación entre el entorno de QGIS y el servidor de IA.
* `mcp_server/`: Servidor local MCP y motor de Machine Learning.
* `agents/`: Definición, coordinador y prompts de los diferentes agentes de IA.

## Instalación

1. Copiar la carpeta `ai_gis_agent` directamente en el directorio de plugins de QGIS:
   * **Windows:** `%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\`
2. Instalar las dependencias de Python necesarias desde el directorio `mcp_server`:
   ```bash
   pip install -r mcp_server/requirements.txt
