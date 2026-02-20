
import os
import subprocess
import time
import socket
import json
import logging
from typing import Optional, Dict, Any

# ==================================================================================================
# CLASE PRINCIPAL DEL PLUGIN
# ==================================================================================================
class TVPlugin:
    def __init__(self, context):
        self.context = context
        self.logger = logging.getLogger("TVPlugin")
        self.logger.info("📺 TV Plugin Inicializado")
        self.plugin_dir = os.path.dirname(os.path.abspath(__file__))
        self.scripts_dir = os.path.join(self.plugin_dir, "scripts")
        self.settings = self._load_settings()
        
    def _load_settings(self) -> Dict[str, Any]:
        """Carga configuración o usa defaults"""
        # 1. Local path (Fina-Ergen root)
        root = os.path.dirname(os.path.dirname(self.plugin_dir))
        local_settings = os.path.join(root, "config", "settings.json")
        
        paths_to_check = [local_settings]
        
        for p in paths_to_check:
            if os.path.exists(p):
                try:
                    with open(p, 'r') as f:
                        self.logger.info(f"📺 Cargando configuración desde: {p}")
                        return json.load(f)
                except Exception as e:
                    self.logger.error(f"Error leyendo settings {p}: {e}")

        # Default si nada funciona (NO INVENTAR DISPOSITIVOS)
        self.logger.error("❌ CRÍTICO: No se pudo cargar settings.json de ninguna ruta conocida.")
        return {"tvs": []}

    def _ensure_adb_connections(self):
        """Intenta conectar a todas las TVs configuradas (Fuerza bruta con timeout corto)"""
        tvs = self.settings.get("tvs", [])
        if isinstance(tvs, dict):
             tvs_list = list(tvs.values())
        else:
             tvs_list = tvs

        for tv in tvs_list:
            ip = tv.get("ip")
            if ip:
                try:
                    # Intentar conectar DIRECTO (sin ping previo que puede fallar)
                    # Timeout 2.0s para dar tiempo a handshake Wi-Fi
                    subprocess.run(["adb", "connect", f"{ip}:5555"], timeout=2.0, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                except: pass

    def _verify_adb_alive(self, ip):
        """Verifica si la conexión ADB está realmente viva ejecutando un comando shell simple."""
        try:
            # Timeout más holgado para evitar falsos negativos en redes congestionadas
            subprocess.run(["adb", "-s", f"{ip}:5555", "shell", "echo", "alive"], 
                           timeout=1.5, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            return True
        except:
            self.logger.warning(f"🧟 Limpiando conexión zombie: {ip}")
            subprocess.run(["adb", "disconnect", f"{ip}:5555"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return False

    def _is_screen_on(self, ip):
        """Verifica si la pantalla de la TV está realmente ENCENDIDA."""
        try:
            # Comando universal para Android: dumpsys power
            # Buscamos 'Display Power: state=ON' o 'mWakefulness=Awake'
            res = subprocess.run(
                ["adb", "-s", f"{ip}:5555", "shell", "dumpsys", "power"], 
                capture_output=True, text=True, timeout=1.5
            )
            output = res.stdout
            
            # Criterios de encendido (cubren varios modelos de Android TV)
            is_awake = "mWakefulness=Awake" in output or "Display Power: state=ON" in output or "mScreenOn=true" in output
            
            if is_awake:
                self.logger.info(f"✅ TV {ip} está ENCENDIDA (Pantalla ON)")
                return True
            else:
                self.logger.info(f"💤 TV {ip} está en STANDBY (Pantalla OFF) - Ignorando...")
                return False
        except Exception as e:
            self.logger.warning(f"⚠️ No pude verificar pantalla de {ip}: {e}")
            self.logger.warning(f"🚫 Descartando TV {ip} por inestabilidad.")
            # Si falla el chequeo, asumimos FALSE. Mejor perder una TV que controlar un fantasma.
            return False

    def _get_connected_devices(self):
        """Devuelve IPs con ADB conectado Y Pantalla Encendida"""
        self._ensure_adb_connections()
        
        try:
            res = subprocess.run(['adb', 'devices'], capture_output=True, text=True, timeout=4)

            connected_and_active = []
            
            for line in res.stdout.split('\n'):
                if '\tdevice' in line:
                    ip = line.split('\t')[0].split(':')[0]
                    
                    # 1. Verificar conexión ADB básica
                    if self._verify_adb_alive(ip):
                        # 2. CRÍTICO: Verificar si la PANTALLA está prendida
                        if self._is_screen_on(ip):
                            connected_and_active.append(ip)
            
            # --- FILTRO DE PRIORIDAD ---
            # Si detectamos la TV Habitación (10), ignoramos la Living (11) porque suele ser un falso positivo (zombie)
            if "192.168.0.10" in connected_and_active and "192.168.0.11" in connected_and_active:
                self.logger.warning("🛡️ Prioridad detectada: TV Habitación online. Ignorando TV Living (posible fantasma).")
                connected_and_active.remove("192.168.0.11")

            self.logger.info(f"🔎 TVs Activas (Pantalla ON): {connected_and_active}")
            return connected_and_active
        except Exception as e:
            self.logger.error(f"Error ADB: {e}")
            return []

    def _get_target_tv(self, command: str, intent_name: str = "") -> dict:
        """
        Determina qué TV controlar basado en:
        1. Mención explícita (Living, Cuarto...)
        2. Estado actual (¿Cuál está prendida?)
        3. Default (si todo lo demás falla)
        """
        tvs = self.settings.get("tvs", [])
        # Normalizar a lista
        if isinstance(tvs, dict):
             tvs_list = [{"name": k, **v} for k, v in tvs.items()]
        else:
             tvs_list = tvs
        
        # DEBUG: Ver qué tenemos
        self.logger.info(f"📋 TVs Cargadas: {[{'name': t.get('name'), 'room': t.get('room'), 'ip': t.get('ip')} for t in tvs_list]}")

        command_low = command.lower()

        # 1. BÚSQUEDA EXPLÍCITA (Prioridad Máxima)
        for tv in tvs_list:
            name = tv.get("name", "").lower()
            room = tv.get("room", "").lower()
            
            # Caso especial: "decodificador" o "deco" fuerza la selección del dispositivo en la habitación Deco
            if room == "deco" and ("decodificador" in command_low or "el deco" in command_low):
                self.logger.info("📺 Selección forzada por palabra clave: Decodificador")
                return tv

            # "en el living", "del cuarto", "la tv de..."
            if (name and (name in command_low)) or (room and (room in command_low)):
                self.logger.info(f"📺 Selección explícita por voz: {tv.get('name')}")
                return tv

        # 2. BÚSQUEDA POR ESTADO (¿Quién está vivo?)
        # Solo aplicable si no estamos intentando prenderla (tv_on siempre usa default o explicito)
        if intent_name != "tv_on":
            online_ips = self._get_connected_devices()
            online_tvs = [tv for tv in tvs_list if tv.get("ip") in online_ips]
            
            self.logger.info(f"🔎 TVs Online Detectadas para {intent_name}: {[t.get('name') for t in online_tvs]}")

            if len(online_tvs) == 1:
                return online_tvs[0]
            elif len(online_tvs) > 1:
                return None # Ambigüedad -> Preguntar
            else:
                 # NO HAY TVS ONLINE
                 # Si el comando es de control (mute, volumen, app), no debemos enviar a un fantasma.
                 self.logger.warning("⚠️ No se detectaron TVs encendidas para comando de control.")
                 # Intentar fallback SOLO si es explícito, de lo contrario abortar para no dar error de ADB.
                 return None 

        # 3. AMBIGÜEDAD FINAL (Para tv_on)
        if intent_name == "tv_on":
             # Aquí sí usamos fallback al primero habilitado (Dormitorio o Living)
             return tvs_list[0] if tvs_list else {}

        return None

        # 2.5 DETECCIÓN VISUAL (CÁMARA / PRESENCIA)
        # Si nadie responde, intentamos ver dónde está el usuario
        try:
             from .vision_helper import detect_user_location
             detected_room = detect_user_location()
             if detected_room:
                 for tv in tvs_list:
                     if detected_room.lower() in tv.get("room", "").lower():
                         self.logger.info(f"👁️ Usuario VISTO en {detected_room} -> Seleccionando TV correspondiente")
                         return tv
        except Exception as e:
             self.logger.warning(f"Error en módulo de visión: {e}")

        # 3. AMBIGÜEDAD FINAL (Nadie prendido, nadie visto, sin nombre explícito)
        # El usuario pidió explícitamente que PREGUNTEMOS en lugar de adivinar con defaults.
        if intent_name == "tv_on" or intent_name == "tv_set_channel":
             self.logger.info("🤷 No sé qué TV controlar. Preguntando al usuario...")
             return None 

        # Para otros comandos (volumen, etc), si está apagada, asumimos la default para no romper todo
        for tv in tvs_list:
            if tv.get("enabled", True): 
                return tv
                
        return tvs_list[0] if tvs_list else {}

    # ----------------------------------------------------------------------------------------------
    # INTERFAZ OBLIGATORIA DEL PLUGIN
    # ----------------------------------------------------------------------------------------------

    def get_intents(self):
        """Devuelve los intents que maneja este plugin"""
        return {
            "tv_on": ["prender la tele", "enciende la tv", "encienda la tv", "enciende la televisión", "encienda la televisión", "prender tv", "activar televisor", "prender la del cuarto", "prender la del comedor"],
            "tv_off": ["apagar la tele", "apaga la tv", "apague la tv", "apagar la televisión", "apaga la televisión", "apague la televisión", "apagar televisor", "apagar la del cuarto", "apagar la del comedor"],
            "tv_volume_up": ["sube el volumen", "subir volumen", "más volumen", "subí el volumen", "aumentar volumen"],
            "tv_volume_down": ["baja el volumen", "bajar volumen", "menos volumen", "bajá el volumen", "disminuir volumen"],
            "tv_mute": ["silenciar tv", "silencio tv", "mute tv", "poner en mude", "quitar sonido tv"],
            "tv_set_volume": ["pon el volumen en", "poner volumen a", "volumen a", "cambiar volumen a", "ajustar volumen a", "volumen en"],
            "tv_channel_scan_fast": ["escanear canales rápido", "busca canales rápido", "actualizar lista de canales"],
            "tv_set_channel": ["pon el canal", "ponga el canal", "cambiar al canal", "ver canal"],
            "tv_list_apps": ["buscar aplicaciones en la tele", "actualizar lista de aplicaciones", "qué aplicaciones tiene la tele"],
            "tv_set_input": ["pone el deco", "quiero ver telecentro", "cambia a hdmi", "pone la tele", "ver aire", "cambia a tv", "ver cable", "ver deco", "ver hdmi"]
        }

    def verify_scripts(self):
        """Verifica que los scripts existan en las carpetas de modelos"""
        # Por ahora verificamos nuestro modelo principal
        base_path = os.path.join(self.plugin_dir, "tcl_32s60a")
        required_scripts = ["tv_on.py", "tv_off.py", "set_channel.py", "list_tv_apps.py", "tv_set_volume.py", "tv_mute.py"]
        
        for script in required_scripts:
            path = os.path.join(base_path, script)
            if not os.path.exists(path):
                self.logger.warning(f"⚠️ Script faltante en tcl_32s60a: {script}")
            else:
                os.chmod(path, 0o755)

    def _get_model_folder(self, tv_type: str) -> str:
        """Mapea el tipo de TV a la carpeta del controlador"""
        # Normalizamos nombres
        tv_type_low = tv_type.lower()
        if tv_type_low in ["tcl", "tcl_32s60a", "androidtv"]:
            return "tcl_32s60a"
        elif tv_type_low in ["sei800tc1", "deco", "telecentro"]:
            return "sei800tc1"
        elif tv_type_low in ["samsung", "tizen"]:
            return "samsung_tizen"
        return "tcl_32s60a" # Fallback

    def _get_script_path(self, target_tv: dict, script_name: str) -> Optional[str]:
        """Resuelve la ruta del script según el modelo de la TV"""
        tv_type = target_tv.get("type", "tcl_32s60a")
        model_folder = self._get_model_folder(tv_type)
        
        # Ajuste para Deco (usamos prefijo deco_ en lugar de tv_)
        if model_folder == "sei800tc1":
            if script_name.startswith("tv_"):
                script_name = script_name.replace("tv_", "deco_")
            elif script_name == "set_channel.py":
                script_name = "deco_set_channel.py"
            elif script_name == "list_tv_apps.py":
                script_name = "list_deco_apps.py"
            elif script_name == "set_input_deco.py":
                script_name = "set_input_deco.py" # Forzar nombre exacto
        
        path = os.path.join(self.plugin_dir, model_folder, script_name)
        
        if os.path.exists(path):
            return path
        
        self.logger.error(f"❌ Script no encontrado para {tv_type}: {path}")
        return None

    def _extract_channel(self, command: str) -> str:
        """Extrae el nombre o número del canal del comando de voz"""
        cmd = command.lower().strip()
        
        # Alias directos hardcodeados de voz que simplifican la vida
        if "fútbol" in cmd or "futbol" in cmd: return "fútbol"
        if "deportivos" in cmd: return "deportes"
        if "noticias" in cmd: return "noticias"
        if "cartoon" in cmd: return "cartoon network"

        # Triggers ordenados por longitud para machear el más específico primero
        triggers = ["pon el canal", "poné el canal", "pone el canal", "cambia al canal", "cambiá al canal", "ver canal", "quiero ver", "pon", "poné", "pone", "ver"]
        
        for t in triggers:
            # Check con espacio o fin de string
            if cmd.startswith(t):
                # Usar slicing para no romper palabras internas
                candidate = cmd[len(t):].strip()
                if candidate: return candidate
                
        return cmd

    def _extract_volume(self, command: str) -> Optional[int]:
        """Extrae el nivel de volumen del comando"""
        import re
        # Busca digitos al final o en medio
        match = re.search(r'(\d+)', command)
        if match:
            return int(match.group(1))
        return None

    def handle_intent(self, intent_name: str, command: str, **kwargs):
        """Manejador principal de comandos"""
        self.logger.info(f"📺 Ejecutando comando TV: {intent_name} | '{command}'")
        target_tv = self._get_target_tv(command, intent_name)
        if target_tv is None:
             # Ambigüedad detectada (varias TVs prendidas)
             rooms = [t.get("room", "Desconocida") for t in self.settings.get("tvs", [])]
             return f"¿En cuál? Disponibles: {', '.join(rooms)}"
        
        if not target_tv:
             # Caso raro (config vacía)
             return "No tengo teles configuradas."

        if intent_name == "tv_on":
            return self.turn_on(target_tv)
        elif intent_name == "tv_off":
            return self.turn_off(target_tv)
        elif intent_name == "tv_volume_up":
            return self.volume_up(target_tv)
        elif intent_name == "tv_volume_down":
            return self.volume_down(target_tv)
        elif intent_name == "tv_mute":
            return self.mute(target_tv)
        elif intent_name == "tv_set_volume":
            level = self._extract_volume(command)
            if level is not None:
                return self.set_volume(target_tv, level)
            return "No entendí a qué volumen ponerlo."
        elif intent_name == "tv_channel_up":
            return self.channel_up(target_tv)
        elif intent_name == "tv_channel_down":
            return self.channel_down(target_tv)
        elif intent_name == "tv_channel_scan_fast":
            return self.scan_channels(target_tv)
        elif intent_name == "tv_list_apps":
            return self.update_app_list(target_tv)
        elif intent_name == "tv_set_channel":
            channel = self._extract_channel(command)
            if channel:
                return self.set_channel(target_tv, channel)
            return "No entendí qué canal poner."
        elif intent_name == "tv_set_input":
            if any(w in command.lower() for w in ["deco", "hdmi", "telecentro"]):
                return self.set_input_deco(target_tv)
            else:
                return self.set_input_tv(target_tv)
        
        return None

    # ----------------------------------------------------------------------------------------------
    # ACCIONES (Despachadores)
    # ----------------------------------------------------------------------------------------------

    def check_connection(self, ip: str) -> bool:
        """Verifica si la TV responde por ADB"""
        try:
            result = subprocess.run(
                ['adb', 'devices'],
                capture_output=True,
                text=True,
                timeout=1
            )
            for line in result.stdout.split('\n'):
                if ip in line and 'device' in line and 'offline' not in line:
                    return True
            return False
        except:
            return False

    def turn_on(self, target_tv: dict):
        """Enciende la TV específica"""
        ip = target_tv.get("ip")
        mac = target_tv.get("mac")

        if ip and self.check_connection(ip):
            return f"La {self._get_tv_label(target_tv)} ya está encendida."

        script = self._get_script_path(target_tv, "tv_on.py")
        if not script: return "No tengo el controlador de encendido para esta tele."
        
        args = ["python3", script]
        if ip: args.extend(["--ip", ip])
        if mac: args.extend(["--mac", mac])
        
        subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return f"Encendiendo {self._get_tv_label(target_tv)}."

    def turn_off(self, target_tv: dict):
        """Apaga la TV específica"""
        ip = target_tv.get("ip")
        if ip and not self.check_connection(ip):
            return f"La {self._get_tv_label(target_tv)} ya parece estar apagada o desconectada."

        script = self._get_script_path(target_tv, "tv_off.py")
        if not script: return "No tengo el controlador de apagado."
        
        args = ["python3", script]
        if ip: args.extend(["--ip", ip])
        
        subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return f"Apagando {self._get_tv_label(target_tv)}."

    def volume_up(self, target_tv: dict):
        ip = target_tv.get("ip")
        if ip and not self.check_connection(ip): return "La tele no responde."
        script = self._get_script_path(target_tv, "tv_volume_up.py")
        if script:
            subprocess.Popen(["python3", script], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return "Subiendo volumen."
        return "No puedo controlar el volumen de esta tele."

    def volume_down(self, target_tv: dict):
        ip = target_tv.get("ip")
        if ip and not self.check_connection(ip): return "La tele no responde."
        script = self._get_script_path(target_tv, "tv_volume_down.py")
        if script:
            subprocess.Popen(["python3", script], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return "Bajando volumen."
        return "No puedo controlar el volumen."

    def mute(self, target_tv: dict):
        ip = target_tv.get("ip")
        if ip and not self.check_connection(ip): return "La tele no responde."
        # Enviamos codigo ADB directo para mute (164)
        subprocess.Popen(["adb", "-s", f"{ip}:5555", "shell", "input", "keyevent", "164"])
        return "Silenciado."

    def set_volume(self, target_tv: dict, level: int):
        ip = target_tv.get("ip")
        if ip and not self.check_connection(ip): return "La tele no responde."
        
        script = self._get_script_path(target_tv, "tv_set_volume.py")
        if script:
            subprocess.Popen(["python3", script, str(level), "--ip", ip], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return f"Poniendo volumen a {level}."
        
        # Fallback ADB directo si no hay script
        cmd = ["adb", "-s", f"{ip}:5555", "shell", "media", "volume", "--show", "--stream", "3", "--set", str(level)]
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return f"Volumen a {level}."

    def channel_up(self, target_tv: dict):
        ip = target_tv.get("ip")
        if ip and not self.check_connection(ip): return "La tele no responde."
        script = self._get_script_path(target_tv, "tv_channel_up.py")
        if script:
            subprocess.Popen(["python3", script], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return "Siguiente canal."
        return "No soportado."

    def channel_down(self, target_tv: dict):
        ip = target_tv.get("ip")
        if ip and not self.check_connection(ip): return "La tele no responde."
        script = self._get_script_path(target_tv, "tv_channel_down.py")
        if script:
            subprocess.Popen(["python3", script], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return "Canal anterior."
        return "No soportado."

    def set_channel(self, target_tv: dict, channel: str):
        """Cambia de canal"""
        script = self._get_script_path(target_tv, "set_channel.py")
        if not script: return "Modelo de TV no soporta cambio de canal."

        ip = target_tv.get("ip")
        if not ip: return "Error de configuración de IP."

        subprocess.Popen(["python3", script, "--ip", ip, "--channel", channel],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        return f"Poniendo {channel} en la tele..."

    def scan_channels(self, target_tv: dict):
        """Escaneo de canales (Ultra Fast)"""
        # Para TCL usamos scan_ultra_fast.py, otros modelos podrían tener scripts diferentes
        # El mapeo se hace buscando el archivo en la carpeta del modelo
        script = self._get_script_path(target_tv, "scan_ultra_fast.py")
        
        # Fallback si no existe ultra fast para este modelo (ej. samsung)
        if not script:
             script = self._get_script_path(target_tv, "scan_generic.py")

        if not script: return "Modelo de TV no soporta escaneo."

        ip = target_tv.get("ip")
        if ip:
             subprocess.Popen(["python3", script, "--ip", ip],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
             return f"Escaneando canales en {self._get_tv_label(target_tv)}..."
        return "No puedo escanear sin IP."

    def update_app_list(self, target_tv: dict):
        """Actualiza lista de apps"""
        script = self._get_script_path(target_tv, "list_tv_apps.py")
        if not script: return "Modelo de TV no soporta lista de apps."

        ip = target_tv.get("ip")
        if ip:
            subprocess.Popen(["python3", script, "--ip", ip], 
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return f"Buscando apps en {self._get_tv_label(target_tv)}..."
        return "Error de IP."

    def _get_tv_label(self, tv_data):
        return tv_data.get('name', 'la tele')


    def set_input_tv(self, target_tv: dict):
        """Cambia a entrada de TV (Aire)"""
        ip = target_tv.get("ip")
        script = self._get_script_path(target_tv, "tv_input.py")
        if not script: return "No tengo controlador de entrada de TV."
        
        args = ["python3", script]
        if ip: args.extend(["--ip", ip])
        
        subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return f"Cambiando a modo Aire en {self._get_tv_label(target_tv)}."

    def set_input_deco(self, target_tv: dict):
        """Cambia a entrada de Deco (HDMI)"""
        ip = target_tv.get("ip")
        script = self._get_script_path(target_tv, "set_input_deco.py")
        if not script: return "No tengo controlador de entrada HDMI."
        
        args = ["python3", script]
        if ip: args.extend(["--ip", ip])
        
        subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return f"Cambiando a modo Deco en {self._get_tv_label(target_tv)}."

    def _get_tv_label(self, tv: dict) -> str:
        """Etiqueta amigable para la TV"""
        name = tv.get("name")
        room = tv.get("room")
        if name: return name
        if room: return f"tele del {room}"
        return "televisión"
