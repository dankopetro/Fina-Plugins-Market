#!/usr/bin/env python3
import subprocess
import os
import sys
import socket
import json
import time
import re
from typing import Optional, Dict, Any, List

# Configuración Ergen
UDP_IP: str = "127.0.0.1"
UDP_PORT: int = 5555
DEFAULT_IP: str = "127.0.0.1:5555"

# Coordenadas ajustadas a ventana de Timbre
BTN_HANGUP_X: int = 360
BTN_HANGUP_Y: int = 760 

def find_waydroid_ip() -> str:
    """Busca dinámicamente la IP asignada a Waydroid"""
    try:
        status_out: str = subprocess.check_output(["waydroid", "status"], text=True, timeout=5) # type: ignore
        # Captura la IP completa 192.168.x.x en un único grupo
        ip_match = re.search(r"IP address:\s+(192\.168\.\d+\.\d+)", status_out)
        if ip_match:
            return f"{ip_match.group(1)}:5555"
    except Exception:
        pass
    return DEFAULT_IP

def emit_event(data: Dict[str, Any]) -> None:
    """Notifica eventos al sistema Ergen vía UDP"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            msg: str = json.dumps(data)
            sock.sendto(msg.encode(), (UDP_IP, UDP_PORT))
    except Exception:
        pass

def main() -> None:
    """Terminación de llamada y limpieza Tuya Smart"""
    waydroid_target: str = find_waydroid_ip()
    print(f"📞 Finalizando llamada en {waydroid_target}...")
    
    # 1. Notificar al sistema
    emit_event({"type": "event", "name": "doorbell-hangup", "module": "doorbell"})
    
    try:
        # 2. Toque en botón de colgar (Rojo)
        subprocess.run(
            ["adb", "-s", waydroid_target, "shell", "input", "tap", str(BTN_HANGUP_X), str(BTN_HANGUP_Y)],
            capture_output=True,
            timeout=5
        ) # type: ignore
        
        print("⏳ Limpiando aplicación y estado...")
        time.sleep(1.5)

        # 3. Force stop de Tuya Smart para liberar recursos
        subprocess.run(["adb", "-s", waydroid_target, "shell", "am", "force-stop", "com.tuya.smart"], capture_output=True, timeout=5) # type: ignore
        # 4. Volver al Home de Android
        subprocess.run(["adb", "-s", waydroid_target, "shell", "input", "keyevent", "KEYCODE_HOME"], capture_output=True, timeout=5) # type: ignore
        
        print("✅ Llamada finalizada y escritorio optimizado.")
        
    except Exception as e:
        print(f"❌ Error en rutina hangup: {e}")
        sys.exit(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    except Exception as fatal:
        print(f"✗ Fatal: {fatal}")
        sys.exit(1)
