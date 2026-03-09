import subprocess
import sys
import time
import socket
import os
import json
import argparse
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

def wake_on_lan(mac_address: str, ip_hint: Optional[str] = None) -> bool:
    """Envía un Magic Packet para despertar la TV vía WoL"""
    try:
        # Limpiar MAC
        mac: str = mac_address.replace(":", "").replace("-", "").strip()
        if len(mac) != 12:
            return False
            
        data: bytes = b'f' * 12 + (bytes.fromhex(mac) * 16)
        
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            # Enviar a broadcast general
            sock.sendto(data, ("255.255.255.255", 9))
            if ip_hint:
                sock.sendto(data, (ip_hint, 9))
        return True
    except Exception as e:
        print(f"⚠️ Error enviando WoL: {e}")
        return False

def check_adb_online(ip: str) -> bool:
    """Verifica si el dispositivo está en línea vía ADB"""
    target: str = f"{ip}:5555" if ":" not in ip else ip
    try:
        res = subprocess.run(["adb", "-s", target, "shell", "echo", "1"], capture_output=True, timeout=2) # type: ignore
        return res.returncode == 0
    except Exception:
        return False

def send_wakeup(ip: str) -> None:
    """Envía el comando de despertar (WAKEUP) vía ADB"""
    target: str = f"{ip}:5555" if ":" not in ip else ip
    print(f"⚡ Despertando TV en {target}...")
    try:
        # KEYCODE_WAKEUP = 224
        subprocess.run(["adb", "-s", target, "shell", "input", "keyevent", "224"], capture_output=True, timeout=3) # type: ignore
        print("✅ Comando WAKEUP enviado.")
    except Exception as e:
        print(f"❌ Error enviando WAKEUP: {e}")

def load_tvs_config() -> List[Dict[str, Any]]:
    """Carga la lista de TVs habilitadas desde settings.json"""
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

def main() -> None:
    """Función principal de encendido inteligente"""
    parser = argparse.ArgumentParser(description="Encendido inteligente TV TCL")
    parser.add_argument("--ip", help="IP específica")
    parser.add_argument("--mac", help="MAC para WoL")
    args = parser.parse_args()

    print("🔌 Fina Ergen: Smart TV ON")
    print("=" * 40)

    targets: List[Dict[str, Any]] = []
    if args.ip:
        targets.append({"ip": args.ip, "mac": args.mac})
    else:
        targets = load_tvs_config()

    if not targets:
        print("❌ No se encontraron TVs configuradas.")
        sys.exit(1)

    for target in targets:
        ip: Optional[str] = target.get("ip")
        mac: Optional[str] = target.get("mac")
        
        if not ip: continue
        
        # 1. Intentar despertar vía WoL
        if mac:
            print(f"○ Enviando Magic Packet (WoL) a {mac}...")
            wake_on_lan(mac, ip_hint=ip)
            
        # 2. Conectar y despertar vía ADB
        target_adb: str = f"{ip}:5555" if ":" not in str(ip) else str(ip)
        print(f"📡 Intentando conectar a {target_adb}...")
        
        try:
            subprocess.run(["adb", "connect", target_adb], capture_output=True, timeout=3) # type: ignore
            if check_adb_online(str(ip)):
                send_wakeup(str(ip))
                print(f"✓ {ip} está encendida.")
                sys.exit(0)
            else:
                print(f"⚠ {ip} no responde a ADB aún...")
        except Exception as e:
            print(f"⚠️ Error en ciclo ADB: {e}")

    print("\n⌛ Ciclo completado sin éxito total. Verificá la red.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    except Exception as fatal:
        print(f"✗ Fatal: {fatal}")
        sys.exit(1)
