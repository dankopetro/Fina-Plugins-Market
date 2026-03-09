import subprocess
import argparse
import sys
from typing import Optional, List, Any

def run_adb_cmd(ip: str, cmd_args: List[str]) -> bool:
    """Ejecuta un comando ADB de forma segura"""
    target: str = f"{ip}:5555" if ":" not in ip else ip
    full_cmd: List[str] = ["adb", "-s", target] + cmd_args
    try:
        subprocess.run(full_cmd, capture_output=True, timeout=5, check=True) # type: ignore
        return True
    except Exception as e:
        print(f"⚠️ Error ejecuntando comando ADB: {e}")
        return False

def set_volume(ip: str, volume_level: int) -> None:
    """Ajusta el volumen absoluto de la TV TCL vía ADB"""
    target: str = f"{ip}:5555" if ":" not in ip else ip
    print(f"🔊 Ajustando volumen a {volume_level} en {target}...")
    
    try:
        # 1. Asegurar conexión rápida
        subprocess.run(["adb", "connect", target], capture_output=True, timeout=3) # type: ignore
        # 2. Comando media volume para stream 3 (MUSIC/MEDIA)
        # --stream 3 = MUSIC/MEDIA, --set <valor>
        volume_cmd: List[str] = ["shell", "media", "volume", "--show", "--stream", "3", "--set", str(volume_level)]
        if run_adb_cmd(ip, volume_cmd):
            print(f"✅ Volumen establecido en {volume_level}.")
    except Exception as e:
        print(f"❌ Error fatal ajustando volumen: {e}")

def main() -> None:
    """Función principal"""
    parser = argparse.ArgumentParser(description="Establecer volumen absoluto en TV TCL")
    parser.add_argument("--ip", required=True, help="IP de la TV")
    parser.add_argument("volume", type=int, help="Nivel de volumen (0-100 o según sistema)")
    args = parser.parse_args()
    
    set_volume(args.ip, args.volume)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    except Exception as fatal:
        print(f"✗ Fatal: {fatal}")
        sys.exit(1)
