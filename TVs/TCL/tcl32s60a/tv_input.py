import subprocess
import sys
import time
import argparse

def switch_to_tv(ip):
    print(f"📺 Cambiando a TV/Aire en {ip}...")
    try:
        # Asegurar conexión
        subprocess.run(["adb", "connect", f"{ip}:5555"], capture_output=True, timeout=3)
        
        # Secuencia descrita por usuario:
        # 1. Abrir menú de entradas (Método Directo APP)
        print("📂 Abriendo Menú de Entradas (TCL Source Manager)...")
        subprocess.run(["adb", "-s", f"{ip}:5555", "shell", "am", "start", "-n", "com.tcl.tv/com.tcl.sourcemenu.sourcemanager.MainActivity"], timeout=5)
        time.sleep(2.5) 
        
        # 2. Asegurar posición inicial (Ir al principio por si acaso)
        # KEYCODE_MOVE_HOME (122) o KEYCODE_DPAD_UP varias veces
        print("⬆️ Reseteando cursor al inicio...")
        subprocess.run(["adb", "-s", f"{ip}:5555", "shell", "input", "keyevent", "122"], timeout=2) 
        time.sleep(0.5)

        # 3. Enter en la primera opción (TV)
        print("✅ Seleccionando TV (Primer Item)...")
        subprocess.run(["adb", "-s", f"{ip}:5555", "shell", "input", "keyevent", "66"], timeout=2) # KEYCODE_ENTER
        
        print("🚀 Cambio a TV/Aire completado.")

    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--ip", required=True, help="IP del dispositivo")
    parser.add_argument("--mac", help="MAC (opcional)")
    args, unknown = parser.parse_known_args()
    
    if args.ip:
        switch_to_tv(args.ip)
    else:
        print("❌ Faltan argumentos: --ip")
