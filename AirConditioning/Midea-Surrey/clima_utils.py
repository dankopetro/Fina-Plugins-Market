#!/usr/bin/env python3
import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

# Configuración de logging
logger = logging.getLogger("ACUtils")

def find_project_root() -> Optional[str]:
    """Busca la raíz del proyecto basándose en marcadores conocidos"""
    curr: Path = Path(__file__).resolve().parent
    for parent in [curr] + list(curr.parents):
        if (parent / "package.json").exists() or (parent / "src" / "App.vue").exists():
            return str(parent)
    return None

def get_ac_config() -> Dict[str, Any]:
    """Carga la configuración del Aire Acondicionado desde múltiples ubicaciones posibles"""
    config: Dict[str, Any] = {
        "ip": "",
        "device_id": 0
    }
    
    xdg_config: Optional[str] = os.environ.get("XDG_CONFIG_HOME")
    config_dir: str = str(Path(xdg_config) / "Fina") if xdg_config else str(Path.home() / ".config" / "Fina")
    proj_root: Optional[str] = find_project_root()

    candidates: List[Optional[str]] = [
        os.path.join(config_dir, "settings.json"),
        os.path.join(proj_root, "config", "settings.json") if proj_root else None
    ]
    
    for path in candidates:
        if path and os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data: Dict[str, Any] = json.load(f)
                    apis: Dict[str, Any] = data.get("apis", {})
                    ac_data: Dict[str, Any] = data.get("ac", {})
                    
                    config["ip"] = str(apis.get("AC_IP", ac_data.get("ip", config["ip"])))
                    config["device_id"] = int(apis.get("AC_ID", ac_data.get("device_id", config["device_id"])))
                    
                    if config["ip"]:
                        logger.info(f"Configuración de AC cargada con éxito desde {path}")
                        break
            except Exception as e:
                logger.warning(f"Error cargando configuración desde {path}: {e}")
                
    return config
