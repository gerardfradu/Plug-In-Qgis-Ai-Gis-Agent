# AI GIS AGENT

AI GIS AGENT is an AI-powered QGIS assistant that connects QGIS with an AI workflow through MCP and supports VS Code / GitHub Copilot integration.

## License and use

AI GIS AGENT is distributed under the **GNU General Public License version 2.0 (GPL-2.0-only)**. No license key, activation or online license validation is required to install or use the plugin.

The GPL grants the freedoms described in the included `LICENSE` file, including the rights to use, study, modify and redistribute the software under the GPL's terms.

## Installation

1. Download the ZIP.
2. In QGIS open **Plugins → Manage and Install Plugins... → Install from ZIP**.
3. Select the downloaded ZIP and install it.
4. Enable **AI GIS AGENT**.

The plugin starts its local MCP bridge automatically on `127.0.0.1:8765`.

## VS Code / GitHub Copilot

Open the **AI GIS AGENT** panel in QGIS and use **Copy Config for VS Code**. Paste the generated configuration into the MCP configuration used by your VS Code / GitHub Copilot setup.

## Support

AI GIS AGENT is available for use under the GNU GPL v2.0 license.

For help, questions or feedback, contact: **aigisagentpro@gmail.com**

Copyright © 2026 Gerard Franch.

## Third-party dependencies

The MCP and optional machine-learning functionality uses external Python packages under their own licenses. These packages are not bundled in this ZIP. See `THIRD-PARTY-NOTICES.md` and `DEPENDENCY-AUDIT.md` for the reviewed dependency licenses and scope.
