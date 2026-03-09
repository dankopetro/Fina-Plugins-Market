#!/usr/bin/env python3
import subprocess
import time
import sys
from typing import Optional, List

# Configuración Base
WAYDROID_ADB_DEFAULT: str = "127.0.0.1:5555"

def check_tuya_packages() -> None:
    """Diagnóstico de paquetes Tuya instalados en Android"""
    print("🔌 Conectando ADB...")
    try:
        subprocess.run(["adb", "connect", WAYDROID_ADB_DEFAULT], capture_output=True, timeout=5) # type: ignore
        time.sleep(1.5)
        
        print("🔍 Buscando paquetes 'tuya'...")
        try:
            # Intento de búsqueda remota directa
            res: str = subprocess.check_output(["adb", "-s", WAYDROID_ADB_DEFAULT, "shell", "pm", "list", "packages"], text=True, timeout=10) # type: ignore
            found: List[str] = [line.strip() for line in res.splitlines() if "tuya" in line.lower()]
            
            if found:
                print("📦 PAQUETES ENCONTRADOS:")
                for pkg in found:
                    print(f"  - {pkg}")
            else:
                print("⚠️ No se detectaron paquetes de Tuya Smart en el sistema.")
        except subprocess.SubprocessError as sub_e:
            print(f"❌ Error de comunicación con el dispositivo: {sub_e}")
        except Exception as e:
            print(f"❌ Error inesperado: {e}")
            
    except Exception as fatal:
        print(f"💥 Fallo crítico de conexión: {fatal}")
        sys.exit(1)

def main() -> None:
    """Función principal de diagnóstico"""
    try:
        check_tuya_packages()
    except KeyboardInterrupt:
        print("\n⏹ Diagnóstico cancelado.")
    except Exception as e:
        print(f"✗ Fatal: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
