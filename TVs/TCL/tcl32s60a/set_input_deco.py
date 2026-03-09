import subprocess
import time
import argparse
import sys
from typing import Optional, List, Any

def switch_to_telecentro(ip: str) -> None:
    """Cambia la entrada de la TV TCL a Telecentro (HDMI) vía ADB"""
    target: str = f"{ip}:5555" if ":" not in ip else ip
    print(f"📺 Cambiando a Telecentro (HDMI) en {target}...")
    
    try:
        # 1. Asegurar conexión rápida
        subprocess.run(["adb", "connect", target], capture_output=True, timeout=3) # type: ignore
        
        # 2. Abrir Menú de Entradas (Actividad específica TCL)
        print("📂 Abriendo Menú de Entradas...")
        subprocess.run(["adb", "-s", target, "shell", "am", "start", "-n", "com.tcl.tv/com.tcl.sourcemenu.sourcemanager.MainActivity"], capture_output=True, timeout=5) # type: ignore
        
        time.sleep(1.2) 
        
        # 3. Navegación (DPAD_DOWN = 20)
        print("⬇️ Seleccionando entrada...")
        subprocess.run(["adb", "-s", target, "shell", "input", "keyevent", "20"], capture_output=True, timeout=2) # type: ignore
        time.sleep(0.4)

        # 4. Confirmar (ENTER = 66)
        print("✅ Confirmando con ENTER...")
        subprocess.run(["adb", "-s", target, "shell", "input", "keyevent", "66"], capture_output=True, timeout=2) # type: ignore
        
        print("🚀 Cambio de entrada completado.")

    except Exception as e:
        print(f"❌ Error cambiando entrada: {e}")

def main() -> None:
    """Función principal"""
    parser = argparse.ArgumentParser(description="Cambiar entrada TV TCL a Deco Telecentro")
    parser.add_argument("--ip", required=True, help="IP de la TV TCL")
    args = parser.parse_args()
    
    switch_to_telecentro(args.ip)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    except Exception as fatal:
        print(f"✗ Fatal: {fatal}")
        sys.exit(1)
