import subprocess
import sys
import time
import argparse
import os
import json
from pathlib import Path
from typing import Optional, List, Dict, Any

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

def load_tvs_config() -> List[Dict[str, Any]]:
    """Carga la lista de IPs de TVs desde settings.json"""
    config_dir: str = get_config_dir()
    proj_root: Optional[str] = find_project_root()
    
    paths: List[str] = [
        os.path.join(config_dir, "settings.json"),
        os.path.join(str(proj_root), "config", "settings.json") if proj_root else ""
    ]
    
    for p in paths:
        if p and os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data: Dict[str, Any] = json.load(f)
                    tvs: Any = data.get("tvs", [])
                    if isinstance(tvs, list):
                        return [t for t in tvs if t.get("enabled", True)]
            except Exception:
                pass
    return []

def check_adb_online(ip: str) -> bool:
    """Verifica si el dispositivo responde vía ADB"""
    target: str = f"{ip}:5555" if ":" not in ip else ip
    try:
        res = subprocess.run(["adb", "-s", target, "shell", "echo", "1"], capture_output=True, timeout=2) # type: ignore
        return res.returncode == 0
    except Exception:
        return False

def send_sleep(ip: str) -> bool:
    """Envía el comando SLEEP a la TV vía ADB"""
    target: str = f"{ip}:5555" if ":" not in ip else ip
    print(f"💤 Apagando TV en {target}...")
    try:
        # KEYCODE_SLEEP = 223
        res = subprocess.run(["adb", "-s", target, "shell", "input", "keyevent", "223"], capture_output=True, timeout=3) # type: ignore
        if res.returncode == 0:
            print("✅ Comando SLEEP enviado.")
            return True
        return False
    except Exception as e:
        print(f"❌ Error enviando SLEEP: {e}")
        return False

def main() -> None:
    """Función principal de apagado inteligente"""
    parser = argparse.ArgumentParser(description="Apagado inteligente TV TCL")
    parser.add_argument("--ip", help="IP específica de la TV")
    args = parser.parse_args()

    print("🔌 Fina Ergen: Smart TV OFF")
    print("=" * 40)

    targets: List[Dict[str, Any]] = []
    if args.ip:
        targets.append({"ip": args.ip})
    else:
        targets = load_tvs_config()

    if not targets:
        print("❌ No se encontraron IPs configuradas.")
        sys.exit(1)

    all_success: bool = True
    for target in targets:
        ip: Optional[str] = target.get("ip")
        if not ip: continue
        
        target_str: str = str(ip)
        target_adb: str = f"{target_str}:5555" if ":" not in target_str else target_str
        
        print(f"📡 Intentando conectar a {target_adb}...")
        try:
            subprocess.run(["adb", "connect", target_adb], capture_output=True, timeout=3) # type: ignore
            if check_adb_online(target_str):
                if send_sleep(target_str):
                    print(f"✓ {target_str} apagada.")
                else:
                    all_success = False
            else:
                print(f"⚠ {target_str} no responde a ADB.")
                all_success = False
        except Exception as e:
            print(f"⚠️ Error en ciclo ADB para {target_str}: {e}")
            all_success = False

    sys.exit(0 if all_success else 1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    except Exception as fatal:
        print(f"✗ Fatal: {fatal}")
        sys.exit(1)
