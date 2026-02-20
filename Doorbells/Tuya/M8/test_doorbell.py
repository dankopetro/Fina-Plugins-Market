
import os
import subprocess
import time
import json

WAYDROID_ADB = "192.168.240.112:5555"
VIRTUAL_SINK_NAME = "FinaVoice"

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

def list_windows():
    log("=== BUSCANDO VENTANAS ===")
    try:
        # wmctrl -l
        res = subprocess.check_output("wmctrl -l", shell=True).decode()
        for line in res.splitlines():
            if "Weston" in line or "Waydroid" in line:
                log(f"🔎 HALLAZGO: {line.strip()}")
            else:
                # log(f"   {line.strip()}")
                pass
    except Exception as e:
        log(f"Error listando ventanas: {e}")
    log("=======================")

def simulate_sequence():
    log("🚀 INICIANDO SIMULACIÓN DE DETECCIÓN DE TIMBRE...")
    
    # 0. Notificar UI
    log("🔔 TIMBRE ACTIVADO! (Offline -> Online) - SIMULADO")
    event_data = {"type": "event", "name": "doorbell-ring", "payload": {}}
    print(json.dumps(event_data), flush=True)
    
    # Notificar vía API para que Fina (main.py) se entere si el script corre aparte
    try:
        import requests
        requests.post("http://127.0.0.1:8000/api/command", json={"name": "doorbell-ring", "payload": {}}, timeout=0.5)
        log("📡 Notificación enviada a la API de Fina.")
    except Exception as e:
        log(f"⚠️ No se pudo notificar a la API (Fina está cerrada?): {e}")
    
    # 1. Asegurar ADB
    log("🥷 Activando Modo Ninja (ADB Connect)...")
    subprocess.run(f"adb connect {WAYDROID_ADB}", shell=True)
    
    # 2. LISTAR VENTANAS PARA DEBUG
    list_windows()
    
    # 3. TRAER WAYDROID AL FRENTE
    log("📈 Intentando traer Waydroid al frente (Matando KDocker)...")
    # 1. Matar KDocker para liberar del Tray
    subprocess.run("pkill -f kdocker", shell=True)
    time.sleep(1)
    # Asegurar Foco (Usamos class 'weston' que es mas robusto)
    subprocess.run("xdotool search --class 'weston' windowmap", shell=True)
    subprocess.run("xdotool search --class 'weston' windowactivate", shell=True)
    
    # --- SACUDIDA PARA DESPERTAR (NUEVO) ---
    log("⚡ Sacudiendo UI para despertar stream...")
    subprocess.run(f"adb -s {WAYDROID_ADB} shell input swipe 300 400 305 405 50", shell=True)
    subprocess.run(f"adb -s {WAYDROID_ADB} shell input swipe 305 405 300 400 50", shell=True)

    # 3. Desbloquear pantalla (Si estaba bloqueada)
    log("🔓 Desbloqueando pantalla...")
    subprocess.run(f"adb -s {WAYDROID_ADB} shell input keyevent 224", shell=True)
    subprocess.run(f"adb -s {WAYDROID_ADB} shell wm dismiss-keyguard", shell=True)
    subprocess.run(f"adb -s {WAYDROID_ADB} shell input swipe 300 700 300 100", shell=True)
    
    # 5. Enfocar App Tuya
    log("📱 Desbloqueado - Esperando que la llamada aparezca sola...")
    # subprocess.run(f"adb -s {WAYDROID_ADB} shell monkey -p com.tuya.smart -c android.intent.category.LAUNCHER 1", shell=True, stdout=subprocess.DEVNULL)
    
    # 6. Esperar UI y Clickear
    log("⏳ Esperando UI (3s)...")
    time.sleep(3)
    
    log("👉 Click (Simulado)...")
    # ... (clicks omitidos para prueba rápida, o incluidos)
    subprocess.run(f"adb -s {WAYDROID_ADB} shell input tap 325 157", shell=True)
    
    # 7. Esperar VIDEO
    log("⏳ Estabilizando llamada (3s)...")
    time.sleep(3)
    
    # 8. MINIMIZAR WAYDROID
    log("📉 Dockeando Waydroid (KDocker)...")
    subprocess.run("xdotool search --class 'weston' | head -n1 | xargs -I {} kdocker -w {} -q -i /usr/share/icons/breeze-dark/status/32/rotation-locked-portrait.svg &", shell=True)
    
    # 9. HABLAR
    log("🗣️ Fina: 'En unos segundos serás atendido. Gracias por esperar.'")
    # Intentar que Fina hable de verdad si la API está lista
    try:
        import requests
        requests.post("http://127.0.0.1:8000/api/state", json={"status": "speaking", "process": "En unos segundos serás atendido. Gracias por esperar."}, timeout=0.2)
    except: pass
    
    # 10. ESPERAR Y COLGAR
    log("⏳ Esperando 20s para que lean el mensaje y luego colgar...")
    time.sleep(20)
    
    log("🔴 Colgando llamada (Botón Rojo)...")
    # 1. Toque en el centro para despertar los controles de Tuya
    subprocess.run(f"adb -s {WAYDROID_ADB} shell input tap 300 400", shell=True)
    time.sleep(0.5)
    # 2. Toque en el botón ROJO de colgar (Abajo a la derecha)
    subprocess.run(f"adb -s {WAYDROID_ADB} shell input tap 360 760", shell=True)
    
    log("🧹 Limpiando Waydroid (Kill App + Home)...")
    time.sleep(1)
    subprocess.run(f"adb -s {WAYDROID_ADB} shell am force-stop com.tuya.smart", shell=True, stderr=subprocess.DEVNULL)
    subprocess.run(f"adb -s {WAYDROID_ADB} shell input keyevent KEYCODE_HOME", shell=True, stderr=subprocess.DEVNULL)
    
    # NOTIFICAR HANGUP A FINA (Esto cierra la ventana roja que viste en la captura)
    log("📡 Enviando señal de COLGAR a Fina...")
    try:
        import requests
        requests.post("http://127.0.0.1:8000/api/command", json={"name": "doorbell-hangup", "payload": {}}, timeout=0.5)
    except: pass
    
    log("✅ Secuencia completada. Fina debería haber cerrado la ventana.")
    print(json.dumps({"type": "event", "name": "doorbell-hangup", "payload": {}}), flush=True)

if __name__ == "__main__":
    simulate_sequence()
