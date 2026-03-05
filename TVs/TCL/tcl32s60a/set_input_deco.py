
import subprocess
import time
import argparse

def switch_to_telecentro(ip):
    print(f"📺 Cambiando a Telecentro (HDMI) en {ip}...")
    try:
        # Asegurar conexión
        subprocess.run(["adb", "connect", f"{ip}:5555"], capture_output=True, timeout=3)
        
        # Secuencia descrita por usuario:
        # 1. Abrir menú de entradas (TCL Source Manager)
        print("📂 Abriendo Menú de Entradas...")
        subprocess.run(["adb", "-s", f"{ip}:5555", "shell", "am", "start", "-n", "com.tcl.tv/com.tcl.sourcemenu.sourcemanager.MainActivity"], timeout=5)
        time.sleep(2.5) 

        # Asegurar posición inicial (KEYCODE_MOVE_HOME)
        subprocess.run(["adb", "-s", f"{ip}:5555", "shell", "input", "keyevent", "122"], timeout=2)
        time.sleep(0.5)
        
        # 2. Bajar 2 veces (Ir a HDMI/Telecentro)
        print("⬇️ Bajando x2...")
        subprocess.run(["adb", "-s", f"{ip}:5555", "shell", "input", "keyevent", "20"], timeout=5) 
        time.sleep(0.8)
        subprocess.run(["adb", "-s", f"{ip}:5555", "shell", "input", "keyevent", "20"], timeout=5) 
        time.sleep(0.8)

        # 3. Enter
        print("✅ Seleccionando Telecentro...")
        subprocess.run(["adb", "-s", f"{ip}:5555", "shell", "input", "keyevent", "66"], timeout=5) # KEYCODE_ENTER
        
        print("🚀 Cambio a Telecentro completado.")

    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--ip", required=True, help="IP del dispositivo")
    parser.add_argument("--mac", help="MAC (opcional)")
    args, unknown = parser.parse_known_args()
    
    if args.ip:
        switch_to_telecentro(args.ip)
    else:
        print("❌ Faltan argumentos: --ip")
