#!/usr/bin/env python3
import os
import json
import subprocess
import sys
import time
import socket
from pathlib import Path
from typing import Optional, Tuple, Dict, List, Any

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

def load_tcl_config() -> Tuple[str, str]:
    """Busca la configuración de la TV TCL en settings.json"""
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
                        for tv in tvs:
                            t_name: str = str(tv.get("name", "")).lower()
                            t_type: str = str(tv.get("type", "")).lower()
                            if "tcl" in t_type or "dormitorio" in t_name:
                                return str(tv.get("ip")), str(tv.get("mac"))
            except Exception:
                pass
    
    # Fallback legacy si no hay config
    return "192.168.0.10", "34:51:80:f9:86:4a"

TARGET_IP, TARGET_MAC = load_tcl_config()

def wake_on_lan(mac_address: str) -> bool:
    """Envía un paquete mágico WoL a la dirección MAC especificada"""
    try:
        clean_mac: str = mac_address.replace(":", "").replace("-", "").strip()
        if len(clean_mac) != 12:
            return False
            
        mac_bytes: bytes = bytes.fromhex(clean_mac)
        magic_packet: bytes = b"\xff" * 6 + mac_bytes * 16
        
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.sendto(magic_packet, ("255.255.255.255", 9))
            
        print(f"⚡ Paquete WoL enviado a {mac_address}")
        return True
    except Exception as e:
        print(f"⚠️ Error enviando WoL: {e}")
        return False

def check_device_connection(ip: str) -> bool:
    """Verifica si el dispositivo está conectado vía ADB y operativo"""
    target: str = f"{ip}:5555" if ":" not in ip else ip
    try:
        res = subprocess.run(["adb", "-s", target, "shell", "echo", "1"], capture_output=True, timeout=2) # type: ignore
        return res.returncode == 0
    except Exception:
        return False

def connect_with_retry_loop(ip: str) -> bool:
    """Ciclo de conexión persistente con WoL integrado"""
    target_adb: str = f"{ip}:5555" if ":" not in ip else ip
    print(f"🚀 Iniciando ciclo de conexión para {target_adb}...")

    # Intentar WoL inicial
    wake_on_lan(TARGET_MAC)
    
    start_time: float = time.time()
    while time.time() - start_time < 60: # Aumentado a 60s para mayor robustez
        try:
            subprocess.run(["adb", "connect", target_adb], capture_output=True, timeout=5) # type: ignore
            if check_device_connection(ip):
                print(f"✓ Conectado exitosamente a {ip}")
                return True
            time.sleep(2)
        except Exception as e:
            print(f"⌛ Esperando respuesta de {ip}... ({e})")
            time.sleep(2)
            
    return False

def send_power_command(ip: str) -> bool:
    """Envía el comando de encendido (Power Key) a la TV"""
    target_adb: str = f"{ip}:5555" if ":" not in ip else ip
    print(f"⚡ Enviando Power Key a {target_adb}...")
    try:
        # KEYCODE_POWER = 26
        res = subprocess.run(["adb", "-s", target_adb, "shell", "input", "keyevent", "26"], capture_output=True, timeout=3) # type: ignore
        return res.returncode == 0
    except Exception as e:
        print(f"❌ Error enviando Power: {e}")
        return False

def main() -> None:
    """Función principal de ejecución"""
    print("🔌 Fina Ergen: TV Power Persistence (TCL)")
    print("=" * 45)
    
    try:
        if connect_with_retry_loop(TARGET_IP):
            time.sleep(1)
            if send_power_command(TARGET_IP):
                print("✅ Operación completada con éxito.")
                sys.exit(0)
            else:
                print("⚠ Error al enviar comando final.")
                sys.exit(1)
        else:
            print("❌ No se pudo establecer conexión tras el ciclo de reintentos.")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n⏹ Operación cancelada.")
        sys.exit(0)
    except Exception as fatal:
        print(f"✗ Fatal: {fatal}")
        sys.exit(1)

if __name__ == "__main__":
    main()
