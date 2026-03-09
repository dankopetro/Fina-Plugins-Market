import subprocess
import os
import sys
import argparse
from typing import Optional, List, Any

def send_key(ip: str, key: str) -> None:
    """Envía un keyevent ADB a la TV TCL"""
    target_ip: str = ip
    if ":" not in target_ip:
        target_ip = f"{target_ip}:5555"
        
    print(f"🔊 Subiendo volumen en {target_ip}...")
    
    try:
        # 1. Asegurar conexión rápida
        subprocess.run(["adb", "connect", target_ip], capture_output=True, timeout=2) # type: ignore
        # 2. Enviar evento de volumen
        adb_cmd: List[str] = ["adb", "-s", target_ip, "shell", "input", "keyevent", key]
        subprocess.run(adb_cmd, capture_output=True, timeout=3) # type: ignore
        print("✓ Comando enviado.")
    except subprocess.TimeoutExpired:
        print(f"⌛ Timeout: La TV en {target_ip} no responde.")
    except Exception as e:
        print(f"❌ Error controlando volumen: {e}")

def main() -> None:
    parser = argparse.ArgumentParser(description="Subir volumen TV TCL vía ADB")
    parser.add_argument("--ip", required=True, help="IP de la TV")
    args = parser.parse_args()

    send_key(args.ip, "KEYCODE_VOLUME_UP")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    except Exception as fatal:
        print(f"✗ Fatal: {fatal}")
        sys.exit(1)
