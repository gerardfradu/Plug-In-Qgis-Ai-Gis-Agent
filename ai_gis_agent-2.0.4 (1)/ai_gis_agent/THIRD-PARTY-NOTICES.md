# AI GIS AGENT — Third-Party Notices

Last reviewed: August 27, 2026

AI GIS AGENT is licensed under the GNU General Public License version 2.0 (GPL-2.0-only).

The packages listed below are **external Python dependencies**. They are not bundled inside this QGIS plugin ZIP. They are installed separately in the user's Python/MCP environment according to `mcp_server/requirements.txt` and the package resolvers' dependency rules.

Each dependency remains subject to its own license. Nothing in the AI GIS AGENT GPLv2 notice changes the license of an independent third-party package.

## Direct runtime dependencies

- **Model Context Protocol Python SDK (`mcp`)** — MIT License.
  - Used by `mcp_server/qgis_mcp_server.py`.
  - Project: https://github.com/modelcontextprotocol/python-sdk
- **pandas** — BSD 3-Clause License.
  - Optional ML functionality.
  - Project: https://pypi.org/project/pandas/
- **scikit-learn** — BSD 3-Clause License.
  - Optional ML functionality.
  - Project: https://pypi.org/project/scikit-learn/
- **joblib** — BSD 3-Clause License.
  - Optional model persistence functionality.
  - Project: https://pypi.org/project/joblib/

## Runtime dependencies pulled by MCP v2

The current MCP v2 package metadata identifies these runtime dependencies (subject to Python/platform markers):

- **mcp-types** — MIT License.
- **anyio** — MIT License.
- **httpx2** — BSD 3-Clause License.
- **pydantic** — MIT License.
- **starlette** — BSD 3-Clause License.
- **python-multipart** — Apache License 2.0.
- **sse-starlette** — BSD 3-Clause License.
- **uvicorn** — BSD 3-Clause License.
- **jsonschema** — MIT License.
- **PyJWT** — MIT License.
- **typing-extensions** — PSF-2.0.
- **typing-inspection** — MIT License.
- **opentelemetry-api** — Apache License 2.0.
- **pywin32** — Python Software Foundation License (Windows only; pywin32 contains a mix of differently licensed code, so its own license files/notices remain authoritative).

The `mcp[cli]` extra additionally installs:

- **typer** — MIT License.
- **python-dotenv** — BSD 3-Clause License.

## Runtime dependencies pulled by scikit-learn

The current scikit-learn package metadata identifies these runtime dependencies:

- **NumPy** — multi-license expression including BSD-3-Clause, 0BSD, MIT, Zlib and CC0-1.0.
- **SciPy** — BSD License.
- **joblib** — BSD 3-Clause License.
- **Narwhals** — MIT License.
- **threadpoolctl** — BSD 3-Clause License.

## Important distribution note

AI GIS AGENT does **not** include copies of the packages above in this ZIP. The notices are provided to identify the licenses of the external packages on which optional/runtime functionality may depend.

If a future release starts physically redistributing any of these packages inside the plugin ZIP, the corresponding package license texts, copyright notices and any additional third-party notices must also be included as required by those licenses.

## License sources reviewed

License information was checked against the package maintainers' current project metadata / PyPI records on August 27, 2026. The package's own license files and notices remain authoritative for any particular version actually installed.
