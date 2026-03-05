#!/usr/bin/env python3
import subprocess
import os
import sys
import socket
import json
import time

# Configuración
# Configuración
UDP_IP = "127.0.0.1"
UDP_PORT = 5555
DEFAULT_IP = "192.168.240.112:5555"

import re
def find_waydroid_ip():
    try:
        status_out = subprocess.getoutput("waydroid status")
        ip_match = re.search(r"IP address:\s+(192\.168\.\d+\.\d+)", status_out)
        if ip_match:
            return f"{ip_match.group(1)}:5555"
    except: pass
    return DEFAULT_IP

WAYDROID_ADB = find_waydroid_ip()

# Coordenadas ajustadas a ventana 455x822
BTN_HANGUP_X = 360
BTN_HANGUP_Y = 760 # Botón rojo para cortar (Ajustado)

def emit(data):
    """Envía eventos al Cerebro Phoenix vía UDP"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        msg = json.dumps(data)
        sock.sendto(msg.encode(), (UDP_IP, UDP_PORT))
    except: pass

def main():
    print(f"📞 Iniciando Terminación de Llamada en {WAYDROID_ADB}...")
    
    # 1. Notificar al sistema
    emit({"type": "event", "name": "doorbell-hangup", "module": "doorbell"})
    
    try:
        # 2. Tap en pantalla (Botón rojo)
        subprocess.run(
            ["adb", "-s", WAYDROID_ADB, "shell", "input", "tap", str(BTN_HANGUP_X), str(BTN_HANGUP_Y)],
            timeout=5
        )
        
        print("⏳ Esperando cierre de llamada...")
        time.sleep(2)

        # 3. Limpieza: Matar Tuya y volver al Home
        print("🧹 Limpiando Waydroid (Kill App + Home)...")
        subprocess.run(["adb", "-s", WAYDROID_ADB, "shell", "am", "force-stop", "com.tuya.smart"], stderr=subprocess.DEVNULL)
        subprocess.run(["adb", "-s", WAYDROID_ADB, "shell", "input", "keyevent", "KEYCODE_HOME"], stderr=subprocess.DEVNULL)
        
        print("✅ Llamada finalizada y escritorio limpio.")
        
        print("✅ Llamada finalizada y recursos liberados.")
        
    except Exception as e:
        print(f"❌ Error en hangup: {e}")

if __name__ == "__main__":
    main()
