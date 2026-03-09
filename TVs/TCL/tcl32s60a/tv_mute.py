import subprocess
import argparse
import sys
from typing import Optional, List, Any

def toggle_mute(ip: str) -> None:
    """Alterna el estado de silencio (mute) en la TV TCL vía ADB"""
    target: str = f"{ip}:5555" if ":" not in ip else ip
    print(f"🔇 Alternando silencio en {target}...")
    
    try:
        # 1. Asegurar conexión rápida
        subprocess.run(["adb", "connect", target], capture_output=True, timeout=3) # type: ignore
        # 2. Enviar KEYCODE_VOLUME_MUTE (164)
        adb_cmd: List[str] = ["adb", "-s", target, "shell", "input", "keyevent", "164"]
        subprocess.run(adb_cmd, capture_output=True, timeout=3) # type: ignore
        print("✓ Comando enviado.")
    except subprocess.TimeoutExpired:
        print(f"⌛ Timeout: La TV en {target} no responde.")
    except Exception as e:
        print(f"❌ Error controlando silencio: {e}")

def main() -> None:
    """Función principal"""
    parser = argparse.ArgumentParser(description="Alternar silencio en TV TCL vía ADB")
    parser.add_argument("--ip", required=True, help="IP de la TV")
    args = parser.parse_args()
    
    toggle_mute(args.ip)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    except Exception as fatal:
        print(f"✗ Fatal: {fatal}")
        sys.exit(1)
