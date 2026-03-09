#!/usr/bin/env python3
import time
import subprocess
import os
import sys
import logging
import json
import re
import socket
import urllib.request
from pathlib import Path
from typing import Optional, Any, List, Dict, Tuple

# Configuración Base
CHECK_INTERVAL: float = 3.0
VIRTUAL_SINK_NAME: str = "FinaVoice"
# IP por defecto de Waydroid (común), pero se puede sobreescrito por config
WAYDROID_ADB_DEFAULT: str = "127.0.0.1:5555"

# Configurar logging profesional
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("DoorbellMonitor")

def get_config_dir() -> str:
    """Obtiene el directorio de configuración de Fina siguiendo estándares XDG"""
    xdg_config = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config:
        return str(xdg_config)
    return str(Path.home() / ".config" / "Fina")

def find_project_root() -> Optional[str]:
    """Busca la raíz del proyecto basándose en package.json"""
    curr = Path(__file__).resolve().parent
    for _ in range(5):
        if (curr / "package.json").exists() or (curr / "src" / "App.vue").exists():
            return str(curr)
        curr = curr.parent
    return None

def find_script(script_rel_path: str) -> Optional[str]:
    """Busca un script en varias ubicaciones posibles del sistema"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    proj_root = find_project_root()
    user_home = str(Path.home())
    
    posibles = [
        os.path.join(script_dir, script_rel_path),
        os.path.join(script_dir, "../../..", script_rel_path),
        os.path.join(user_home, "Descargas/Fina-Ergen", script_rel_path),
        os.path.join("/usr/lib/fina-ergen", script_rel_path),
        os.path.join(os.getcwd(), script_rel_path)
    ]
    for p in posibles:
        if p and os.path.exists(p):
            return p
    return None

def load_doorbell_config() -> Tuple[str, bool]:
    """Carga la configuración del timbre desde settings.json"""
    config_dir: str = get_config_dir()
    proj_root: Optional[str] = find_project_root()
    doorbell_ip: str = ""
    configured: bool = False

    paths: List[str] = [
        os.path.join(config_dir, "settings.json"),
        os.path.join(str(proj_root), "config", "settings.json") if proj_root else ""
    ]
    
    for p in paths:
        if p and os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data: Dict[str, Any] = json.load(f)
                    # 1. Mirar en APIS
                    timeout_ip = data.get("apis", {}).get("TIMBRE_IP")
                    if timeout_ip:
                        doorbell_ip = str(timeout_ip)
                        configured = True
                    
                    # 2. Mirar en Devices
                    devices: Any = data.get("devices", [])
                    if isinstance(devices, list):
                        for d in devices:
                            d_type: str = str(d.get("type", "")).lower()
                            d_name: str = str(d.get("name", "")).lower()
                            if any(x in d_type or x in d_name for x in ["timbre", "doorbell", "tuya"]):
                                doorbell_ip = str(d.get("ip", doorbell_ip))
                                configured = True
                                break
            except Exception:
                pass
    return doorbell_ip, configured

def wait_for_adb(target: str, timeout: int = 60) -> bool:
    """Espera a que el dispositivo ADB esté listo"""
    start: float = time.time()
    while time.time() - start < timeout:
        try:
            subprocess.run(["adb", "connect", target], capture_output=True, timeout=5) # type: ignore
            res = subprocess.run(["adb", "devices"], capture_output=True, text=True, timeout=3) # type: ignore
            if target in res.stdout and "device" in res.stdout and "offline" not in res.stdout:
                return True
        except Exception:
            pass
        time.sleep(2)
    return False

def setup_virtual_audio() -> None:
    """Configura el sink virtual para aislamiento de audio"""
    try:
        # 1. Sink Virtual
        check_sink = subprocess.run(f"pactl list short sinks | grep {VIRTUAL_SINK_NAME}", shell=True, capture_output=True)
        if check_sink.returncode != 0:
            logger.info("🎛️ Creando Sink Virtual Ergen...")
            subprocess.run(["pactl", "load-module", "module-null-sink", f"sink_name={VIRTUAL_SINK_NAME}", f"sink_properties=device.description=Fina_Virtual_Mic"], capture_output=True) # type: ignore

        # 2. Loopback
        check_loop = subprocess.run(f"pactl list short modules | grep module-loopback | grep {VIRTUAL_SINK_NAME}.monitor", shell=True, capture_output=True)
        if check_loop.returncode != 0:
            logger.info("🎛️ Creando Loopback Virtual...")
            subprocess.run(["pactl", "load-module", "module-loopback", f"source={VIRTUAL_SINK_NAME}.monitor"], capture_output=True) # type: ignore
            
    except Exception as e:
        logger.error(f"⚠️ Error setup audio: {e}")

def is_device_online(ip: str) -> bool:
    """Verifica conectividad IP rápida"""
    if not ip: return False
    try:
        res = subprocess.run(["ping", "-c", "1", "-W", "1", ip], capture_output=True, timeout=2) # type: ignore
        return res.returncode == 0
    except Exception:
        return False

def speak_local(text: str) -> None:
    """Feedback de voz local (intenta usar Fina, fallback a print)"""
    logger.info(f"🗣️ Notificación: {text}")
    try:
        from utils import speak # type: ignore
        speak(text)
    except ImportError:
        print(f"(LOG) {text}")

def ensure_infrastructure() -> bool:
    """Asegura que Waydroid y Weston estén operativos"""
    try:
        check = subprocess.run(["pgrep", "-f", "waydroid session"], capture_output=True) # type: ignore
        if check.returncode != 0:
            logger.info("🚀 Iniciando sistema Android oculto...")
            script_path: Optional[str] = find_script("scripts/start_hidden_system.sh")
            if not script_path:
                logger.error("❌ No se encontró script de arranque.")
                return False

            env = os.environ.copy()
            env["DISPLAY"] = ":0"
            proj_root = find_project_root()
            subprocess.Popen(
                ["bash", script_path], 
                env=env, 
                stdout=subprocess.DEVNULL, 
                stderr=subprocess.DEVNULL, 
                start_new_session=True,
                cwd=proj_root
            )
            
            if not wait_for_adb(WAYDROID_ADB_DEFAULT):
                logger.error("❌ Error: Waydroid no respondió.")
                return False

            time.sleep(5)
            # Desbloqueo y pre-calentamiento
            subprocess.run(["adb", "-s", WAYDROID_ADB_DEFAULT, "shell", "input", "keyevent", "224"], capture_output=True) # type: ignore
            subprocess.run(["adb", "-s", WAYDROID_ADB_DEFAULT, "shell", "wm", "dismiss-keyguard"], capture_output=True) # type: ignore
            subprocess.run(["adb", "-s", WAYDROID_ADB_DEFAULT, "shell", "am", "start", "-n", "com.tuya.smart/com.smart.ThingSplashActivity"], capture_output=True) # type: ignore
            time.sleep(5)
            subprocess.run(["adb", "-s", WAYDROID_ADB_DEFAULT, "shell", "input", "keyevent", "3"], capture_output=True) # type: ignore
            
            # Lanzar Streamer
            streamer_p: Optional[str] = find_script("streamer.py")
            if streamer_p:
                proj_root = find_project_root()
                subprocess.Popen(
                    [sys.executable, streamer_p], 
                    stdout=subprocess.DEVNULL, 
                    stderr=subprocess.DEVNULL, 
                    start_new_session=True,
                    cwd=proj_root
                )
        return True
    except Exception as e:
        logger.error(f"⚠️ Error infraestructura: {e}")
        return False

def api_notify(endpoint: str, data: Dict[str, Any]) -> None:
    """Envía comandos a la API local de Fina"""
    try:
        url: str = f"http://127.0.0.1:18000/api/{endpoint}"
        req = urllib.request.Request(url, data=json.dumps(data).encode(), headers={'Content-Type': 'application/json'}, method='POST')
        with urllib.request.urlopen(req, timeout=0.5) as _:
            pass
    except Exception:
        pass

def monitor_loop() -> None:
    """Bucle principal de monitoreo reactivo"""
    doorbell_ip, configured = load_doorbell_config()
    if not configured:
        logger.info("ℹ️ Monitoreo cancelado: Timbre no configurado.")
        return

    logger.info("⏳ Esperando estabilización de sistema (10s)...")
    time.sleep(10)

    if not ensure_infrastructure():
        logger.error("❌ Fallo crítico en infraestructura Android.")
        return

    setup_virtual_audio()
    logger.info(f"🕵️ Vigilancia armada en {doorbell_ip}")

    was_online: bool = is_device_online(doorbell_ip)
    last_trigger: float = 0.0
    failures: int = 0

    while True:
        try:
            # Auto-Heal Streamer
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.2)
                if s.connect_ex(('127.0.0.1', 8555)) != 0:
                    str_path = find_script("streamer.py")
                    if str_path:
                        subprocess.Popen([sys.executable, str_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)

            current_online: bool = is_device_online(doorbell_ip)
            
            if current_online:
                failures = 0
                now: float = time.time()
                # Detección de flanco de subida (Ring)
                if not was_online:
                    logger.info("🔔 ¡TIMBRE ACTIVADO!")
                    if (now - last_trigger) > 60:
                        last_trigger = now
                        speak_local("Alguien toca el timbre.")
                        api_notify("command", {"name": "doorbell-ring", "payload": {}})
                        print(json.dumps({"type": "event", "name": "doorbell-ring", "payload": {}}), flush=True)

                        # Atender vía Waydroid
                        subprocess.run(["adb", "connect", WAYDROID_ADB_DEFAULT], capture_output=True, timeout=5) # type: ignore
                        # Activar Ventana
                        subprocess.run("pkill -f kdocker", shell=True) # type: ignore
                        subprocess.run("xdotool search --class 'weston' windowmap windowactivate", shell=True) # type: ignore
                        
                        # Simular atención
                        time.sleep(2)
                        for _ in range(2):
                            subprocess.run(["adb", "-s", WAYDROID_ADB_DEFAULT, "shell", "input", "tap", "325", "157"], capture_output=True) # type: ignore
                            time.sleep(1)
                        
                        # Comunicación (TTS)
                        # A. PTT (Presionar para hablar)
                        ptt_process = None
                        try:
                            # Iniciar PTT (Swipe largo para mantener presionado)
                            ptt_process = subprocess.Popen(["adb", "-s", WAYDROID_ADB_DEFAULT, "shell", "input", "swipe", "228", "643", "228", "643", "10000"])
                            time.sleep(1.5) # Margen para que Android abra el micro
                            
                            # Enrutamiento de audio (Intento rápido)
                            try:
                                virtual_source = subprocess.check_output("pactl list short sources | grep 'FinaVoice.monitor' | cut -f1", shell=True).decode().strip()
                                output = subprocess.check_output("pactl list source-outputs", shell=True).decode()
                                if "Waydroid" in output:
                                    blocks = output.split("Salida de fuente #")
                                    for b in blocks:
                                        if "Waydroid" in b:
                                            waydroid_id = b.split("\n")[0].strip()
                                            break
                                if waydroid_id and virtual_source:
                                    subprocess.run(f"pactl move-source-output {waydroid_id} {virtual_source}", shell=True)
                            except Exception: pass
                        except Exception as e:
                            logger.warning(f"⚠️ Error iniciando PTT: {e}")

                        # B. HABLAR (La frase de Fina)
                        h = int(time.strftime("%H"))
                        saludo = "buenos días" if 6 <= h < 12 else "buenas tardes" if 12 <= h < 20 else "buenas noches"
                        mensaje = f"{saludo}. En unos segundos serás atendido. Gracias."
                        
                        logger.info(f"🗣️ Fina: '{mensaje}'")
                        
                        api_notify("state", {"status": "speaking", "process": mensaje})

                        # TTS Real
                        os.environ["PULSE_SINK"] = VIRTUAL_SINK_NAME
                        try: speak_local(mensaje)
                        except Exception: pass
                        finally:
                            os.environ.pop("PULSE_SINK", None)
                        
                        # C. FINALIZAR VOZ
                        time.sleep(1.0) # Buffer
                        if ptt_process: ptt_process.terminate()
                        logger.info("👆 PTT Soltado.")

                        # 8. ESPERAR Y COLGAR
                        logger.info("⏳ Esperando 20s para estabilizar y luego colgar...")
                        time.sleep(20)

                        # 6. COLGAR Y CERRAR (SIEMPRE se ejecuta)
                        logger.info("🔴 Finalizando llamada...")
                        # 1. Toque en el centro para despertar los controles de Tuya
                        subprocess.run(["adb", "-s", WAYDROID_ADB_DEFAULT, "shell", "input", "tap", "300", "400"], capture_output=True) # type: ignore
                        time.sleep(0.5)
                        # 2. Toque en el botón ROJO de colgar (Abajo a la derecha)
                        subprocess.run(["adb", "-s", WAYDROID_ADB_DEFAULT, "shell", "input", "tap", "360", "760"], capture_output=True) # type: ignore
                        
                        logger.info("🧹 Limpiando Waydroid (Kill App + Home)...")
                        time.sleep(1) # Pequeña pausa para que procese el colgado
                        subprocess.run(["adb", "-s", WAYDROID_ADB_DEFAULT, "shell", "am", "force-stop", "com.tuya.smart"], capture_output=True) # type: ignore
                        subprocess.run(["adb", "-s", WAYDROID_ADB_DEFAULT, "shell", "input", "keyevent", "KEYCODE_HOME"], capture_output=True) # type: ignore
                        
                        # Notificar Cierre a Fina (API + Stdout)
                        logger.info("📡 Notificando colgado a la interfaz...")
                        api_notify("command", {"name": "doorbell-hangup", "payload": {}})
                        print(json.dumps({"type": "event", "name": "doorbell-hangup", "payload": {}}), flush=True)
                        logger.info("✅ Ciclo de timbre completado exitosamente.")
                        
                        # Cooldown para no repetir
                        last_trigger = time.time()
                        logger.info("⏳ Iniciando cooldown de 60s...")
                        time.sleep(60)

                    else:
                        logger.info("⏳ Ignorando (Cooldown).")
                    
                    was_online = True
            
            else:
                # OFFLINE DETECTADO
                # LÓGICA ANTI-REBOTE: Requiere 3 fallos consecutivos
                failures += 1
                if failures >= 3:
                    if was_online:
                        logger.info("💤 Timbre desconectado (Confirmado).")
                    was_online = False
            
            time.sleep(CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"❌ Error en monitor: {e}")
            time.sleep(5)

if __name__ == "__main__":
    try:
        monitor_loop()
    except KeyboardInterrupt:
        logger.info("⏹ Monitoreo detenido.")
    except Exception as fatal:
        logger.error(f"💥 Fatal: {fatal}")
        sys.exit(1)
