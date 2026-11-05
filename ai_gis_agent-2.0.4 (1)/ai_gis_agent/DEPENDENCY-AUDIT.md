# AI GIS AGENT — Dependency Audit

**Audit date:** August 27, 2026
**Plugin version:** 1.0.9

## Scope

This audit covers dependencies declared by `mcp_server/requirements.txt` and the runtime dependency trees identified by the current MCP v2 and scikit-learn package metadata.

## Findings

| Package | Role | License | Status |
|---|---|---|---|
| mcp | MCP runtime | MIT | Reviewed |
| pandas | Optional ML | BSD-3-Clause | Reviewed |
| scikit-learn | Optional ML | BSD-3-Clause | Reviewed |
| joblib | Optional ML/model persistence | BSD-3-Clause | Reviewed |
| mcp-types | MCP runtime | MIT | Reviewed |
| anyio | MCP async runtime | MIT | Reviewed |
| httpx2 | MCP HTTP client | BSD-3-Clause | Reviewed |
| pydantic | MCP models/validation | MIT | Reviewed |
| starlette | MCP HTTP server transport | BSD-3-Clause | Reviewed |
| python-multipart | MCP HTTP transport | Apache-2.0 | Reviewed |
| sse-starlette | MCP SSE transport | BSD-3-Clause | Reviewed |
| uvicorn | MCP ASGI server | BSD-3-Clause | Reviewed |
| jsonschema | MCP schema validation | MIT | Reviewed |
| PyJWT | MCP authorization | MIT | Reviewed |
| typing-extensions | Python typing support | PSF-2.0 | Reviewed |
| typing-inspection | Pydantic typing support | MIT | Reviewed |
| opentelemetry-api | MCP tracing API | Apache-2.0 | Reviewed |
| pywin32 | Windows stdio support | PSF / mixed notices | Reviewed with package notices authoritative |
| typer | MCP CLI extra | MIT | Reviewed |
| python-dotenv | MCP CLI extra | BSD-3-Clause | Reviewed |
| NumPy | scikit-learn dependency | BSD-3-Clause + other permissive licenses | Reviewed |
| SciPy | scikit-learn dependency | BSD | Reviewed |
| Narwhals | scikit-learn dependency | MIT | Reviewed |
| threadpoolctl | scikit-learn dependency | BSD-3-Clause | Reviewed |

## Distribution conclusion

No dependency identified in this audit is, by its stated package license, inherently incompatible with distributing the AI GIS AGENT source code under GPLv2.

This is a license-compatibility review, not a legal opinion. The exact license files/notices of the exact package versions installed or redistributed remain authoritative.

## Versioning

`mcp_server/requirements.txt` uses an upper bound on the MCP major version to avoid silently switching to a future incompatible major API. Dependency updates should be reviewed again before each Product release.
