# -*- coding: utf-8 -*-
"""Visible project-file backups for AI GIS AGENT."""
import os
import shutil
from datetime import datetime
from qgis.core import QgsProject

def create_project_backup(project_path=None):
    """Create a timestamped copy of the saved QGIS project file.

    The backup is stored next to the project in AI_GIS_AGENT_Backups/.
    This backs up the project file itself; externally referenced layer data
    is not copied by this function.
    """
    if project_path is None:
        project_path = QgsProject.instance().fileName()
    if not project_path:
        raise ValueError("Please save the QGIS project before creating a backup.")
    project_path = os.path.abspath(project_path)
    if not os.path.isfile(project_path):
        raise ValueError("The current QGIS project file could not be found.")
    project_dir = os.path.dirname(project_path)
    backup_root = os.path.join(project_dir, "AI_GIS_AGENT_Backups")
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backup_dir = os.path.join(backup_root, "backup_" + stamp)
    os.makedirs(backup_dir, exist_ok=True)
    backup_path = os.path.join(backup_dir, os.path.basename(project_path))
    shutil.copy2(project_path, backup_path)
    return {"backup_dir": backup_dir, "backup_path": backup_path}
