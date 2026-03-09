#!/usr/bin/env python3
import os
import subprocess
import time
import json
import re
from typing import Optional, Dict, Any, List

# Configuración Base
WAYDROID_ADB_DEFAULT: str = "127.0.0.1:5555"
VIRTUAL_SINK_NAME: str = "FinaVoice"

def get_waydroid_ip() -> str:
    """Detecta la IP de Waydroid dinámicamente"""
    try:
        status_out: str = subprocess.check_output(["waydroid", "status"], text=True, timeout=5) # type: ignore
        ip_match = re.search(r"IP address:\s+(192\.168\.\d+\.\d+)", status_out)
        if ip_match:
            return f"{ip_match.group(1)}:5555"
    except Exception:
        pass
    return WAYDROID_ADB_DEFAULT

def log_event(msg: str) -> None:
    """Log de eventos con timestamp"""
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

def list_system_windows() -> None:
    """Enumera ventanas activas para depuración (requiere wmctrl)"""
    log_event("=== BUSCANDO VENTANAS DEL SISTEMA ===")
    try:
        res: str = subprocess.check_output(["wmctrl", "-l"], text=True, timeout=5) # type: ignore
        for line in res.splitlines():
            if any(x in line for x in ["Weston", "Waydroid"]):
                log_event(f"🔎 HALLAZGO: {line.strip()}")
    except Exception as e:
        log_event(f"⚠️ Error listando ventanas: {e}")
    log_event("======================================")

def simulate_doorbell_sequence() -> None:
    """Secuencia completa de simulación de timbre"""
    waydroid_target: str = get_waydroid_ip()
    log_event(f"🚀 Iniciando simulación en {waydroid_target}")
    
    # 0. Notificar al sistema Fina
    log_event("🔔 ¡TIMBRE ACTIVADO! (Simulado)")
    event_payload: Dict[str, Any] = {"type": "event", "name": "doorbell-ring", "payload": {}}
    print(json.dumps(event_payload), flush=True)
    
    try:
        import urllib.request
        url: str = "http://127.0.0.1:18000/api/command"
        req = urllib.request.Request(url, data=json.dumps({"name": "doorbell-ring", "payload": {}}).encode(), headers={'Content-Type': 'application/json'}, method='POST')
        with urllib.request.urlopen(req, timeout=1.0) as _:
            log_event("📡 API Ergen notificada.")
    except Exception as e:
        log_event(f"⚠️ API no disponible: {e}")
    
    # 1. Preparar ADB
    log_event("🥷 Activando conexión ADB...")
    subprocess.run(["adb", "connect", waydroid_target], capture_output=True, timeout=5) # type: ignore
    
    # 2. Debug visual
    list_system_windows()
    
    # 3. Traer interfaz al frente
    log_event("📈 Enfocando Waydroid (Limpiando KDocker)...")
    subprocess.run(["pkill", "-f", "kdocker"], capture_output=True) # type: ignore
    time.sleep(1)
    subprocess.run("xdotool search --class 'weston' windowmap windowactivate", shell=True) # type: ignore
    
    # 4. Interactuar con UI Android
    log_event("⚡ Despertando pantalla Android...")
    subprocess.run(["adb", "-s", waydroid_target, "shell", "input", "swipe", "300", "400", "305", "405", "50"], capture_output=True) # type: ignore
    subprocess.run(["adb", "-s", waydroid_target, "shell", "input", "keyevent", "224"], capture_output=True) # type: ignore
    subprocess.run(["adb", "-s", waydroid_target, "shell", "wm", "dismiss-keyguard"], capture_output=True) # type: ignore
    
    log_event("⏳ Esperando aparición de interfaz (3s)...")
    time.sleep(3)
    
    log_event("👉 Toque de atención...")
    subprocess.run(["adb", "-s", waydroid_target, "shell", "input", "tap", "325", "157"], capture_output=True) # type: ignore
    
    log_event("⏳ Estabilizando flujo de video (3s)...")
    time.sleep(3)
    
    log_event("📉 Minimizando Waydroid al Tray...")
    subprocess.run("xdotool search --class 'weston' | head -n1 | xargs -I {} kdocker -w {} -q -i /usr/share/icons/breeze-dark/status/32/rotation-locked-portrait.svg &", shell=True) # type: ignore
    
    # 5. Feedback de Voz
    log_event("🗣️ Fina: 'Iniciando protocolo de atención automática.'")
    try:
        url_state: str = "http://127.0.0.1:18000/api/state"
        msg: Dict[str, Any] = {"status": "speaking", "process": "Simulación de timbre activa."}
        req_v = urllib.request.Request(url_state, data=json.dumps(msg).encode(), headers={'Content-Type': 'application/json'}, method='POST')
        with urllib.request.urlopen(req_v, timeout=0.5) as _:
            pass
    except Exception:
        pass
    
    # 6. Espera y Finalización
    log_event("⏳ Simulación de duración de llamada (15s)...")
    time.sleep(15)
    
    log_event("🔴 Finalizando llamada (Botón Rojo)...")
    subprocess.run(["adb", "-s", waydroid_target, "shell", "input", "tap", "300", "400"], capture_output=True) # type: ignore
    time.sleep(0.5)
    subprocess.run(["adb", "-s", waydroid_target, "shell", "input", "tap", "360", "760"], capture_output=True) # type: ignore
    
    log_event("🧹 Limpiando recursos y volviendo a Home...")
    time.sleep(1)
    subprocess.run(["adb", "-s", waydroid_target, "shell", "am", "force-stop", "com.tuya.smart"], capture_output=True) # type: ignore
    subprocess.run(["adb", "-s", waydroid_target, "shell", "input", "keyevent", "KEYCODE_HOME"], capture_output=True) # type: ignore
    
    log_event("✅ Simulación completada con éxito.")
    print(json.dumps({"type": "event", "name": "doorbell-hangup", "payload": {}}), flush=True)

if __name__ == "__main__":
    try:
        simulate_doorbell_sequence()
    except KeyboardInterrupt:
        log_event("⏹ Simulación interrumpida por el usuario.")
    except Exception as fatal:
        log_event(f"❌ Error fatal en simulación: {fatal}")
