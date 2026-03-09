import tinytuya # type: ignore
import json
import sys
import os
from pathlib import Path
from typing import Optional, Dict, Any, List

def get_config_dir() -> str:
    """Obtiene el directorio de configuración de Fina siguiendo estándares XDG"""
    xdg_config = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config:
        return str(xdg_config)
    return str(Path.home() / ".config" / "Fina")

def find_project_root() -> Optional[str]:
    """Busca la raíz del proyecto basándose en package.json"""
    curr = Path(__file__).resolve().parent
    for _ in range(5):
        if (curr / "package.json").exists() or (curr / "src" / "App.vue").exists():
            return str(curr)
        curr = curr.parent
    return None

def get_battery() -> str:
    """Nivel de batería del timbre inalámbrico Tuya vía Cloud API"""
    config_dir: str = get_config_dir()
    proj_root: Optional[str] = find_project_root()
    
    paths: List[str] = [
        os.path.join(config_dir, "tuya_config.json"),
        os.path.join(str(proj_root), "config", "tuya_config.json") if proj_root else ""
    ]
    
    config_path: str = ""
    for p in paths:
        if p and os.path.exists(p):
            config_path = p
            break
            
    if not config_path:
        return "N/A"
        
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config: Dict[str, Any] = json.load(f)

        # Conectar a Tuya Cloud
        cloud = tinytuya.Cloud(
            apiRegion=config.get("region_code"),
            apiKey=config.get("access_id"),
            apiSecret=config.get("access_secret"),
            uid=config.get("uid")
        )

        status: Any = cloud.getstatus(config.get("device_id"))
        if isinstance(status, dict) and status.get("success"):
            results: List[Dict[str, Any]] = status.get("result", [])
            for dp in results:
                if dp.get("code") == "wireless_electricity":
                    return str(dp.get("value"))
        return "N/A"
    except Exception:
        return "N/A"

def main() -> None:
    """Función principal"""
    battery: str = get_battery()
    print(battery)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    except Exception:
        sys.exit(1)
