import json
import os

from qgis.PyQt.QtCore import Qt, QUrl
from qgis.PyQt.QtWidgets import QApplication
from qgis.PyQt.QtGui import QFont, QDesktopServices
from qgis.PyQt.QtWidgets import (
    QAction,
    QDockWidget,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .bridge import QGISCommandServer


class AIGisAgentPanel(QDockWidget):
    def __init__(self, plugin):
        super().__init__("AI GIS AGENT", plugin.iface.mainWindow())
        self.plugin = plugin
        self.setObjectName("AIGISAgentPanel")
        # Compatible with QGIS 3 / PyQt5 and QGIS 4 / PyQt6.
        try:
            left_dock = Qt.DockWidgetArea.LeftDockWidgetArea
            right_dock = Qt.DockWidgetArea.RightDockWidgetArea
        except AttributeError:
            left_dock = getattr(Qt, 'LeftDockWidgetArea')
            right_dock = getattr(Qt, 'RightDockWidgetArea')
        self.setAllowedAreas(left_dock | right_dock)

        root = QWidget()
        layout = QVBoxLayout(root)

        title = QLabel("AI GIS AGENT")
        title.setFont(QFont("Sans Serif", 16, QFont.Weight.Bold))
        layout.addWidget(title)

        subtitle = QLabel("AI-powered GIS assistance for QGIS. No license key or activation is required.")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        status = QLabel("🟢 AI GIS AGENT is ready. The MCP bridge starts automatically with QGIS.")
        status.setWordWrap(True)
        layout.addWidget(status)

        self.copy_button = QPushButton("📋 Copy Config for VS Code")
        self.copy_button.clicked.connect(self.copy_config)
        layout.addWidget(self.copy_button)

        self.web_button = QPushButton("🌐 Open AI GIS AGENT Website")
        self.web_button.setToolTip("Open the official AI GIS AGENT website in your browser")
        self.web_button.clicked.connect(self.open_website)
        layout.addWidget(self.web_button)

        info = QTextEdit()
        info.setReadOnly(True)
        info.setPlainText(
            "AI GIS AGENT is distributed under the GNU General Public License v2.0.\n\n"
            "No license key or activation is required to install or use the plugin.\n\n"
            "1. Install the plugin in QGIS.\n"
            "2. Keep QGIS running.\n"
            "3. Copy the MCP configuration into VS Code / GitHub Copilot if you want to use the MCP integration.\n\n"
            "AI GIS AGENT is available for use under the GNU GPL v2.0 license.\n\n"
            "AI-generated results should always be reviewed and validated by the user."
        )
        layout.addWidget(info)

        layout.addStretch(1)
        self.setWidget(root)

    def copy_config(self):
        text = json.dumps(self.plugin.mcp_config(), ensure_ascii=False, indent=2)
        QApplication.clipboard().setText(text)
        QMessageBox.information(self, "AI GIS AGENT", "MCP settings copied to the clipboard.")

    def open_website(self):
        QDesktopServices.openUrl(QUrl("https://aigisagent.netlify.app/"))


class AIGisPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.server = None
        self.action = None
        self.panel = None

    def initGui(self):
        self.action = QAction("AI GIS AGENT", self.iface.mainWindow())
        self.action.triggered.connect(self.toggle_panel)
        self.iface.addPluginToMenu("&AI GIS AGENT", self.action)

        self.panel = AIGisAgentPanel(self)
        # Use the same Qt5/Qt6 compatibility handling when adding the dock.
        try:
            right_dock = Qt.DockWidgetArea.RightDockWidgetArea
        except AttributeError:
            right_dock = getattr(Qt, 'RightDockWidgetArea')
        self.iface.addDockWidget(right_dock, self.panel)
        self.panel.show()
        self.panel.raise_()

        # The plugin starts directly. No license or activation is required.
        self.start()

    def unload(self):
        self.stop_server()
        if self.panel:
            self.iface.removeDockWidget(self.panel)
            self.panel.deleteLater()
            self.panel = None
        if self.action:
            self.iface.removePluginMenu("&AI GIS AGENT", self.action)
            self.action.deleteLater()
            self.action = None

    def toggle_panel(self):
        if self.panel:
            self.panel.setVisible(not self.panel.isVisible())
            if self.panel.isVisible():
                self.panel.raise_()
                self.panel.refresh_status()

    def mcp_config(self):
        # Keep the VS Code / GitHub Copilot configuration format used by the
        # original plugin: an absolute path to the bundled MCP server.
        plugin_root = os.path.dirname(os.path.abspath(__file__))
        server_path = os.path.join(plugin_root, "mcp_server", "qgis_mcp_server.py")
        return {
            "servers": {
                "AI GIS AGENT": {
                    "type": "stdio",
                    "command": "python",
                    "args": [server_path],
                    "env": {},
                }
            }
        }

    def start(self):
        if self.server and self.server.is_running:
            return
        self.server = QGISCommandServer(
            self.iface,
            host="127.0.0.1",
            port=8765,
        )
        try:
            self.server.start()
            self.iface.messageBar().pushSuccess("AI GIS AGENT", "Agent available on 127.0.0.1:8765")
        except Exception as exc:
            self.server = None
            self.iface.messageBar().pushCritical("AI GIS AGENT", f"Could not start the server: {exc}")

    def stop_server(self):
        if self.server:
            self.server.stop()
            self.server = None
