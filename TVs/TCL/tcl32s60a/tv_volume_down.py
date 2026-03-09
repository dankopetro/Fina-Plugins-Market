import subprocess
import argparse
import sys
from typing import Optional, List, Any

def send_key(ip: str, key_code: str) -> None:
    """Envía un código de tecla a la TV TCL vía ADB"""
    target: str = f"{ip}:5555" if ":" not in ip else ip
    print(f"🔉 Enviando tecla {key_code} a {target}...")
    
    try:
        # 1. Asegurar conexión rápida
        subprocess.run(["adb", "connect", target], capture_output=True, timeout=3) # type: ignore
        # 2. Enviar evento de tecla
        adb_cmd: List[str] = ["adb", "-s", target, "shell", "input", "keyevent", key_code]
        subprocess.run(adb_cmd, capture_output=True, timeout=3) # type: ignore
        print("✓ Comando enviado.")
    except subprocess.TimeoutExpired:
        print(f"⌛ Timeout: La TV en {target} no responde.")
    except Exception as e:
        print(f"❌ Error enviando comando: {e}")

def main() -> None:
    """Función principal"""
    parser = argparse.ArgumentParser(description="Bajar volumen en TV TCL vía ADB")
    parser.add_argument("--ip", required=True, help="IP de la TV")
    args = parser.parse_args()
    
    send_key(args.ip, "KEYCODE_VOLUME_DOWN")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    except Exception as fatal:
        print(f"✗ Fatal: {fatal}")
        sys.exit(1)
