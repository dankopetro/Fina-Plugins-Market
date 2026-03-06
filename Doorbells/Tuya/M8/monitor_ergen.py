import time
import subprocess
import os
import sys
import logging

# Configuración
DOORBELL_IP = "192.168.0.5"
CHECK_INTERVAL = 3.0
VIRTUAL_SINK_NAME = "FinaVoice"
WAYDROID_ADB = "192.168.240.112:5555"

def wait_for_adb(timeout=60):
    """Espera a que el dispositivo ADB esté listo y devuelve True/False"""
    start = time.time()
    try:
        while time.time() - start < timeout:
            # 1. Intentar connect
            subprocess.run(f"adb connect {WAYDROID_ADB}", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            # 2. Verificar listado
            res = subprocess.run("adb devices", shell=True, stdout=subprocess.PIPE).stdout.decode()
            if WAYDROID_ADB in res and "\tdevice" in res:
                return True
            time.sleep(2)
    except: pass
    return False

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

# RUTA AL PROYECTO (Dinámica y Resiliente)
script_dir = os.path.dirname(os.path.abspath(__file__))
# Fallback hardcodeado para la máquina del usuario
USER_HOME = os.path.expanduser("~")
REPO_FALLBACK = os.path.join(USER_HOME, "Descargas/Fina-Ergen")

def find_script(script_rel_path):
    """Busca un script en varias ubicaciones posibles"""
    posibles = [
        os.path.join(script_dir, "../../..", script_rel_path), # Si esta en la repo/plugins
        os.path.join(REPO_FALLBACK, script_rel_path),         # Repo del usuario
        os.path.join("/usr/lib/fina-ergen", script_rel_path),   # Instalado
        os.path.join(os.getcwd(), script_rel_path)            # CWD
    ]
    for p in posibles:
        if os.path.exists(p):
            return p
    return None

PROJECT_ROOT = REPO_FALLBACK # Default
sys.path.append(PROJECT_ROOT)

# --- CARGAR CONFIGURACIÓN ---
DOORBELL_CONFIGURED = False
try:
    def get_config_dir():
        xdg_config = os.environ.get("XDG_CONFIG_HOME")
        if xdg_config:
            return os.path.join(xdg_config, "Fina")
        return os.path.expanduser("~/.config/Fina")

    config_dir = get_config_dir()
    paths = [
        os.path.join(config_dir, "settings.json"),
        os.path.join(PROJECT_ROOT, "config/settings.json")
    ]
    for p in paths:
        if os.path.exists(p):
            import json
            with open(p, "r") as f:
                data = json.load(f)
            
            # 1. Mirar en APIS
            timeout_ip = data.get("apis", {}).get("TIMBRE_IP")
            if timeout_ip:
                DOORBELL_IP = timeout_ip
                DOORBELL_CONFIGURED = True
            
            # 2. Mirar en Devices (Filtro estricto para evitar cámaras IP genéricas)
            devices = data.get("devices", [])
            for d in devices:
                d_type = str(d.get("type", "")).lower()
                d_name = str(d.get("name", "")).lower()
                
                # Criterios: Que sea un Timbre explícito o que use la marca Tuya
                es_timbre = d_type in ["timbre", "doorbell"] or "timbre" in d_name or "doorbell" in d_name
                es_tuya = "tuya" in d_type or "tuya" in d_name
                
                if es_timbre or es_tuya:
                    DOORBELL_IP = d.get("ip", DOORBELL_IP)
                    DOORBELL_CONFIGURED = True
                    break
except: pass
# ----------------------------

# Importar utils o definir fallbacks
try:
    from utils import speak, show_doorbell_stream
except ImportError:
    def speak(text, model=None):
        print(f"🗣️ (Fallback) {text}", flush=True)
        # Fallback simple
        try:
           import json
           print(json.dumps({"type": "event", "name": "fina-state", "payload": {"status": "speaking", "process": text}}), flush=True)
        except: pass
    def show_doorbell_stream(model=None):
        pass

def setup_virtual_audio():
    """Configura el sink virtual para audio limpio"""
    try:
        # 1. Verificar/Crear SINK
        cmd_check_sink = f"pactl list short sinks | grep {VIRTUAL_SINK_NAME}"
        if subprocess.run(cmd_check_sink, shell=True, stdout=subprocess.DEVNULL).returncode != 0:
            print("🎛️ Creando Audio Virtual (Sink)...")
            cmd_create = f"pactl load-module module-null-sink sink_name={VIRTUAL_SINK_NAME} sink_properties=device.description=Fina_Virtual_Mic"
            subprocess.run(cmd_create, shell=True)

        # 2. Verificar/Crear LOOPBACK (Para que escuches lo que pasa en el virtual)
        # Buscamos un módulo loopback que tenga nuestro sink como source
        cmd_check_loop = f"pactl list short modules | grep module-loopback | grep {VIRTUAL_SINK_NAME}.monitor"
        if subprocess.run(cmd_check_loop, shell=True, stdout=subprocess.DEVNULL).returncode != 0:
            print("🎛️ Creando Audio Virtual (Loopback)...")
            # Dejar que PulseAudio decida el sink de salida (default)
            cmd_loop = f"pactl load-module module-loopback source={VIRTUAL_SINK_NAME}.monitor"
            subprocess.run(cmd_loop, shell=True, stderr=subprocess.DEVNULL)
            
        # 3. Restaurar Microfono Default
        try:
            # Intentar buscar MICRÓFONO INTERNO (PCI) primero
            mic_cmd = "pactl list short sources | grep 'input' | grep -v 'monitor' | grep 'pci' | head -n1 | cut -f2"
            res = subprocess.run(mic_cmd, shell=True, stdout=subprocess.PIPE).stdout.decode().strip()
            
            # Si no hay interno, buscar CUALQUIERA (USB, etc.)
            if not res:
                mic_cmd = "pactl list short sources | grep 'input' | grep -v 'monitor' | head -n1 | cut -f2"
                res = subprocess.run(mic_cmd, shell=True, stdout=subprocess.PIPE).stdout.decode().strip()

            if res:
                 subprocess.run(f"pactl set-default-source {res}", shell=True)
                 print(f"🎤 Default Source restaurado a: {res}")
        except Exception as ex:
             print(f"⚠️ No se pudo restaurar default mic: {ex}")
            
    except Exception as e:
        print(f"⚠️ Error setup audio: {e}")

def is_online(ip):
    try:
        res = subprocess.run(["ping", "-c", "1", "-W", "1", ip], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return res.returncode == 0
    except:
        return False

def get_audio_ids():
    """Devuelve (virtual_source, mic_source) o (None, '58')"""
    try:
        # Virtual Source (Monitor del Null Sink)
        v_cmd = f"pactl list short sources | grep '{VIRTUAL_SINK_NAME}.monitor' | cut -f1"
        virtual = subprocess.check_output(v_cmd, shell=True).decode().strip()
        
        # Mic Físico (Input analógico default)
        m_cmd = "pactl list short sources | grep 'analog-stereo' | grep 'input' | head -n1 | cut -f1"
        mic = subprocess.check_output(m_cmd, shell=True).decode().strip()
        
        return virtual, mic
    except:
        return None, "58"

def find_waydroid_stream():
    """Intenta encontrar el ID del stream de grabación de Waydroid"""
    for _ in range(10): # 5 intentos rápidos (0.1s * 10 = 1s total) - Ajustado a 10 para dar margen
        try:
            output = subprocess.check_output("pactl list source-outputs", shell=True).decode()
            if "Waydroid" in output:
                # Parseo bruto pero efectivo
                blocks = output.split("Salida de fuente #")
                for block in blocks:
                    if "Waydroid" in block:
                        return block.split("\n")[0].strip()
        except:
            pass
        time.sleep(0.1)
    return None

def ensure_android_environment():
    """Verifica si Waydroid/Weston están corriendo. Si no, los inicia."""
    try:
        # Chequear si waydroid session está activa
        # Buscamos procesos de waydroid
        check = subprocess.run("pgrep -f 'waydroid session'", shell=True, stdout=subprocess.DEVNULL)
        
        # FORZAR SIEMPRE EL ARRANQUE (El script bash maneja la limpieza de duplicados)
        # Esto soluciona el problema de detecciones falsas o zombies que impiden que Weston se abra
        if True: # Simular que siempre se necesita iniciar
            print("🚀 Iniciando infraestructura Android (Weston + Waydroid)...")
            # Definir entorno gráfico explícito para Weston
            env = os.environ.copy()
            env["DISPLAY"] = ":0"
            env["XDG_RUNTIME_DIR"] = f"/run/user/{os.getuid()}"
            
            # Ejecutar el script de arranque en segundo plano
            script_path = find_script("scripts/start_hidden_system.sh")
            
            if not script_path:
                print(f"ERROR: No encuentro scripts/start_hidden_system.sh en ninguna ruta conocida.")
                return

            print(f"📂 Usando script: {script_path}")
            subprocess.Popen(["bash", script_path], 
                           env=env, # Inyectar display
                           stdout=subprocess.DEVNULL, 
                           stderr=subprocess.DEVNULL,
                           start_new_session=True)
            
            # Darle tiempo para arrancar (es pesado) - ESPERA INTELIGENTE
            print("⏳ Esperando conexión ADB (máx 60s)...")
            
            if not wait_for_adb(60):
                print("❌ ERROR CRITICO: Waydroid no arrancó a tiempo.")
                return 

            print("✅ Waydroid conectado. Esperando 5s para estabilizar sistema...")
            time.sleep(5)

            # Desbloqueo explícito por si acaso
            subprocess.run(f"adb -s {WAYDROID_ADB} shell input keyevent 224", shell=True)
            subprocess.run(f"adb -s {WAYDROID_ADB} shell wm dismiss-keyguard", shell=True)
            
            # PRE-LAUNCH TUYA SMART (Y minimizar)
            print("📱 Pre-calentando Tuya Smart (SplashActivity)...")
            # Usamos am start directo a la Activity correcta
            subprocess.run(f"adb -s {WAYDROID_ADB} shell am start -n com.tuya.smart/com.smart.ThingSplashActivity", shell=True)
            time.sleep(5)
            # Volver a Home
            subprocess.run(f"adb -s {WAYDROID_ADB} shell input keyevent 3", shell=True)
            
            # --- LANZAR STREAMER (NUEVO) ---
            print("🎥 Iniciando servidor de Video Stream...")
            streamer_path = find_script("streamer.py")
            if streamer_path:
                subprocess.Popen([sys.executable, streamer_path], 
                               stdout=subprocess.DEVNULL, 
                               stderr=subprocess.DEVNULL,
                               start_new_session=True)
                print("✅ Streamer iniciado.")
            else:
                print("⚠️ No se encontró streamer.py en las rutas conocidas.")

            # ELIMINADO: No minimizamos manualmente aquí porque start_hidden_system.sh YA lo hizo con KDocker.
            print("✅ Tuya Smart lista en segundo plano.")

    except Exception as e:
        print(f"⚠️ Error verificando entorno Android: {e}")

def monitor_loop():
    # 0. Verificar si el plugin debe activarse
    if not DOORBELL_CONFIGURED:
        print("ℹ️ Plugin Doorbell: No hay un timbre configurado en settings.json. Saltando inicio de Android.")
        return

    # 0. Retraso de cortesía para dejar que Fina (main.py) arranque su audio primero
    print("⏳ Esperando 10s para no saturar audio al inicio... (Originalmente 20)")
    time.sleep(10)

    # 1. Asegurar infraestructura
    ensure_android_environment()
    
    setup_virtual_audio()
    print(f"🕵️ Vigilando timbre {DOORBELL_IP}...")
    
    # ESTADO INICIAL: Chequear si ya está online al arrancar
    # Si ya está online, asumimos que es estado basal o residual y NO activamos.
    # Solo activaremos cuando pase de Offline -> Online.
    if is_online(DOORBELL_IP):
        print("⚠️ Timbre detectado ONLINE al inicio. Esperando a que se duerma para armar sistema...")
        was_online = True
    else:
        print("✅ Timbre dormido. Sistema ARMADO.")
        was_online = False

    last_seen = 0
    consecutive_failures = 0
    
    while True:
        try:
            online = is_online(DOORBELL_IP)
            
            if online:
                # Si volvemos a estar online, reseteamos el contador de fallos
                consecutive_failures = 0
                
                now = time.time()
                # Flanco de subida (Se conectó)
                if not was_online:
                    print("\n🔔 ¡TIMBRE ACTIVADO! (Offline -> Online)")
                    
                    # Cooldown 45s (Suficiente para nueva visita, protegido por anti-rebote)
                    if (now - last_seen) > 45:
                        print("🚀 INICIANDO SECUENCIA DE ATENCIÓN...")
                        
                        # 1. Feedback Auditivo Local
                        speak("Atención. Alguien toca el timbre.", None)

                        # NOTIFICAR A LA UI (Importante para que se abra la ventana)
                        event_data = {"type": "event", "name": "doorbell-ring", "payload": {}}
                        print(json.dumps(event_data), flush=True)
                        
                        # Redundancia vía API
                        try:
                            import requests
                            requests.post("http://127.0.0.1:18000/api/command", json={"name": "doorbell-ring", "payload": {}}, timeout=0.2)
                        except: pass
                        
                        # 2. Despertar y Preparar Entorno (ADB)
                        print("🥷 Activando Modo Ninja...")
                        subprocess.run(f"adb connect {WAYDROID_ADB}", shell=True, stdout=subprocess.DEVNULL)
                        
                        # ACTIVAR VENTANA WAYDROID (Para que se vea al atender)
                        print("📈 Trayendo Waydroid al frente (Matando KDocker)...")
                        # 1. Matar KDocker para liberar del Tray (si estaba ahí)
                        subprocess.run("pkill -f kdocker", shell=True)
                        time.sleep(1)
                        # 2. Asegurar Foco (Usamos class 'weston' que es mas robusto)
                        subprocess.run("xdotool search --class 'weston' windowmap", shell=True)
                        subprocess.run("xdotool search --class 'weston' windowactivate", shell=True)

                        # --- SACUDIDA PARA DESPERTAR (NUEVO) ---
                        print("⚡ Sacudiendo UI para despertar stream...")
                        # Pequeños toques/swipes en zona segura para que Android detecte actividad
                        subprocess.run(f"adb -s {WAYDROID_ADB} shell input swipe 300 400 305 405 50", shell=True)
                        subprocess.run(f"adb -s {WAYDROID_ADB} shell input swipe 305 405 300 400 50", shell=True)

                        # Wake & Unlock
                        subprocess.run(f"adb -s {WAYDROID_ADB} shell input keyevent 224", shell=True)
                        subprocess.run(f"adb -s {WAYDROID_ADB} shell wm dismiss-keyguard", shell=True)
                        subprocess.run(f"adb -s {WAYDROID_ADB} shell input swipe 300 700 300 100", shell=True)
                        
                        # Traer App Tuya (YA ESTABA ABIERTA - NO RE-LANZAR)
                        # print("📱 Enfocando Tuya Smart...")
                        # subprocess.run(f"adb -s {WAYDROID_ADB} shell monkey -p com.tuya.smart -c android.intent.category.LAUNCHER 1", shell=True, stdout=subprocess.DEVNULL)

                        # 3. Intentar Atender (Clicks PRECISOS)
                        print("⏳ Esperando UI (3s)...")
                        time.sleep(3)
                        
                        success = True 
                        
                        # RE-INSERTAMOS INTENTOS DE CLICK (Para que veas al fantasma actuar)
                        for i in range(3):
                            print(f"👉 Intento #{i+1}...")
                            subprocess.run(f"adb -s {WAYDROID_ADB} shell input tap 325 157", shell=True)
                            time.sleep(0.5)
                            subprocess.run(f"adb -s {WAYDROID_ADB} shell input keyevent 5", shell=True)
                            time.sleep(1.5)
                        
                        if success:

                            # Esperar a que conecte audio/video (3s visible Waydroid)
                            print("⏳ Estabilizando llamada (3s)...")
                            time.sleep(3)
                            
                            # MINIMIZAR WAYDROID (Para ver Fina)
                            print("📉 Dockeando Waydroid (KDocker)...")
                            # Usamos kdocker sobre la clase 'weston' para volver al tray
                            subprocess.run("xdotool search --class 'weston' | head -n1 | xargs -I {} kdocker -w {} -q -i /usr/share/icons/breeze-dark/status/32/rotation-locked-portrait.svg &", shell=True)
                            
                            # 4. Secuencia de Audio y Comunicación (Hablar)
                            print("🎙️ Iniciando comunicación con el visitante...")
                            
                            # A. PTT (Presionar para hablar)
                            ptt_process = None
                            waydroid_id = None
                            try:
                                # Iniciar PTT (Swipe largo para mantener presionado)
                                ptt_process = subprocess.Popen(["adb", "-s", WAYDROID_ADB, "shell", "input", "swipe", "228", "643", "228", "643", "10000"])
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
                                except: pass
                            except Exception as e:
                                print(f"⚠️ Error iniciando PTT: {e}")

                            # B. HABLAR (La frase de Fina)
                            h = int(time.strftime("%H"))
                            saludo = "buenos días" if 6 <= h < 12 else "buenas tardes" if 12 <= h < 20 else "buenas noches"
                            mensaje = f"{saludo}. En unos segundos serás atendido. Gracias."
                            
                            print(f"🗣️ Fina: '{mensaje}'")
                            
                            # Notificar visualmente a la UI
                            try:
                                import requests
                                requests.post("http://127.0.0.1:18000/api/state", json={"status": "speaking", "process": mensaje}, timeout=0.2)
                            except: pass

                            # TTS Real
                            os.environ["PULSE_SINK"] = VIRTUAL_SINK_NAME
                            try: speak(mensaje, None)
                            except: pass
                            finally:
                                if "PULSE_SINK" in os.environ: del os.environ["PULSE_SINK"]
                            
                            # C. FINALIZAR VOZ
                            time.sleep(1.0) # Buffer
                            if ptt_process: ptt_process.terminate()
                            print("👆 PTT Soltado.")

                            # 8. ESPERAR Y COLGAR
                            print("⏳ Esperando 20s para estabilizar y luego colgar...")
                            time.sleep(20)

                            # 6. COLGAR Y CERRAR (SIEMPRE se ejecuta)
                            print("🔴 Finalizando llamada...")
                            # 1. Toque en el centro para despertar los controles de Tuya
                            subprocess.run(f"adb -s {WAYDROID_ADB} shell input tap 300 400", shell=True)
                            time.sleep(0.5)
                            # 2. Toque en el botón ROJO de colgar (Abajo a la derecha)
                            subprocess.run(f"adb -s {WAYDROID_ADB} shell input tap 360 760", shell=True)
                            
                            print("🧹 Limpiando Waydroid (Kill App + Home)...")
                            time.sleep(1) # Pequeña pausa para que procese el colgado
                            subprocess.run(f"adb -s {WAYDROID_ADB} shell am force-stop com.tuya.smart", shell=True, stderr=subprocess.DEVNULL)
                            subprocess.run(f"adb -s {WAYDROID_ADB} shell input keyevent KEYCODE_HOME", shell=True, stderr=subprocess.DEVNULL)
                            
                            # Notificar Cierre a Fina (API + Stdout)
                            print("📡 Notificando colgado a la interfaz...")
                            try:
                                import requests
                                requests.post("http://127.0.0.1:18000/api/command", json={"name": "doorbell-hangup", "payload": {}}, timeout=0.5)
                            except: pass
                            
                            print(json.dumps({"type": "event", "name": "doorbell-hangup", "payload": {}}), flush=True)
                            print("✅ Ciclo de timbre completado exitosamente.")
                            
                            # Cooldown para no repetir
                            last_seen = time.time()
                            print("⏳ Iniciando cooldown de 60s...")
                            time.sleep(60)

                    else:
                        print("⏳ Ignorando (Cooldown).")
                    
                    was_online = True
            
            else:
                # OFFLINE DETECTADO
                # LÓGICA ANTI-REBOTE: Requiere 3 fallos consecutivos
                consecutive_failures += 1
                if consecutive_failures >= 3:
                    if was_online:
                        print("\n💤 Timbre desconectado (Confirmado).")
                        was_online = False
                else:
                    pass
            
            time.sleep(CHECK_INTERVAL)
            
        except Exception as e:
            print(f"❌ Error en bucle principal: {e}")
            time.sleep(5)

if __name__ == "__main__":
    monitor_loop()
