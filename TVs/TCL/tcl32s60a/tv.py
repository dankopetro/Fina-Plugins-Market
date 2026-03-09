#!/usr/bin/env python3
import os
import subprocess
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List

# ==================================================================================================
# CLASE PRINCIPAL DEL PLUGIN TCL 32S60A
# ==================================================================================================
class TVPlugin:
    """Plugin para control de Televisores TCL y Android TV vía ADB"""
    
    def __init__(self, context: Any) -> None:
        self.context: Any = context
        self.logger: logging.Logger = logging.getLogger("TVPlugin")
        self.plugin_dir: str = os.path.dirname(os.path.abspath(__file__))
        self.settings: Dict[str, Any] = self._load_settings()
        self.logger.info("📺 TV Plugin (TCL/Android TV) Inicializado")
        
    def _get_config_path(self) -> str:
        """Determina la ruta del archivo de configuración siguiendo estándares XDG"""
        xdg_config: Optional[str] = os.environ.get("XDG_CONFIG_HOME")
        if xdg_config:
            return str(Path(xdg_config) / "Fina" / "settings.json")
        return str(Path.home() / ".config" / "Fina" / "settings.json")

    def _find_project_root(self) -> Optional[str]:
        """Busca la raíz del proyecto basándose en marcadores conocidos"""
        curr: Path = Path(self.plugin_dir).resolve()
        for parent in [curr] + list(curr.parents):
            if (parent / "package.json").exists() or (parent / "src" / "App.vue").exists():
                return str(parent)
        return None

    def _load_settings(self) -> Dict[str, Any]:
        """Carga configuración desde múltiples ubicaciones posibles de forma robusta"""
        standard_path: str = self._get_config_path()
        proj_root: Optional[str] = self._find_project_root()
        fallback_path: Optional[str] = str(Path(proj_root) / "config" / "settings.json") if proj_root else None
        
        candidates: List[Optional[str]] = [standard_path, fallback_path]
        
        for path in candidates:
            if path and os.path.exists(path):
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        data: Dict[str, Any] = json.load(f)
                        self.logger.info(f"✅ Settings cargados desde: {path}")
                        return data
                except Exception as e:
                    self.logger.error(f"⚠️ Error leyendo {path}: {e}")

        self.logger.error("❌ No se encontró settings.json en ninguna ubicación conocida.")
        return {"tvs": []}

    def _ensure_adb_connections(self) -> None:
        """Estabiliza conexiones ADB con todos los dispositivos configurados"""
        tvs_data: Any = self.settings.get("tvs", [])
        tvs_list: List[Dict[str, Any]] = []
        
        if isinstance(tvs_data, dict):
            tvs_list = list(tvs_data.values())
        elif isinstance(tvs_data, list):
            tvs_list = tvs_data

        for tv in tvs_list:
            ip: Optional[str] = tv.get("ip")
            if ip:
                try:
                    # Timeout corto para no bloquear la inicialización
                    subprocess.run(["adb", "connect", f"{ip}:5555"], capture_output=True, timeout=2.0) # type: ignore
                except Exception:
                    pass

    def _verify_connection(self, ip: str) -> bool:
        """Verifica la salud de la conexión ADB y limpia sesiones huérfanas"""
        try:
            subprocess.run(["adb", "-s", f"{ip}:5555", "shell", "echo", "1"], 
                           capture_output=True, timeout=1.5, check=True) # type: ignore
            return True
        except Exception:
            subprocess.run(["adb", "disconnect", f"{ip}:5555"], capture_output=True) # type: ignore
            return False

    def _is_screen_active(self, ip: str) -> bool:
        """Utiliza PowerManager para determinar si la pantalla está encendida"""
        try:
            res: subprocess.CompletedProcess = subprocess.run(
                ["adb", "-s", f"{ip}:5555", "shell", "dumpsys", "power"], 
                capture_output=True, text=True, timeout=2.0
            ) # type: ignore
            out: str = res.stdout
            return any(x in out for x in ["mWakefulness=Awake", "Display Power: state=ON", "mScreenOn=true"])
        except Exception:
            return False

    def _get_active_ips(self) -> List[str]:
        """Obtiene lista de IPs con ADB activo y pantalla encendida"""
        self._ensure_adb_connections()
        active_ips: List[str] = []
        try:
            res: subprocess.CompletedProcess = subprocess.run(['adb', 'devices'], capture_output=True, text=True, timeout=3) # type: ignore
            for line in res.stdout.splitlines():
                if '\tdevice' in line:
                    ip: str = line.split('\t')[0].split(':')[0]
                    if self._verify_connection(ip) and self._is_screen_active(ip):
                        active_ips.append(ip)
        except Exception as e:
            self.logger.error(f"Error enumerando dispositivos ADB: {e}")
        return active_ips

    def _resolve_target_tv(self, query: str, intent: str) -> Optional[Dict[str, Any]]:
        """Inteligencia de resolución de objetivo basada en voz, estado y visión"""
        tvs_data: Any = self.settings.get("tvs", [])
        tvs_list: List[Dict[str, Any]] = []
        
        if isinstance(tvs_data, dict):
            tvs_list = [{"name": k, **v} for k, v in tvs_data.items() if isinstance(v, dict)]
        elif isinstance(tvs_data, list):
            tvs_list = tvs_data
        
        query_low: str = query.lower()

        # 1. Resolución Explícita (Voz)
        for tv in tvs_list:
            name: str = str(tv.get("name", "")).lower()
            room: str = str(tv.get("room", "")).lower()
            if (name and name in query_low) or (room and room in query_low):
                return tv
            if room == "deco" and any(x in query_low for x in ["decodificador", "el deco", "deco"]):
                return tv

        # 2. Resolución por Estado (Dispositivo Encendido)
        if intent != "tv_on":
            active_ips: List[str] = self._get_active_ips()
            candidates: List[Dict[str, Any]] = [tv for tv in tvs_list if tv.get("ip") in active_ips]
            if len(candidates) == 1:
                return candidates[0]

        # 3. Fallback: Primer dispositivo habilitado
        for tv in tvs_list:
            if tv.get("enabled", True):
                return tv
        
        return tvs_list[0] if tvs_list else None

    def get_intents(self) -> Dict[str, List[str]]:
        """Define el diccionario de intents de lenguaje natural para este plugin"""
        return {
            "tv_on": ["prender la tele", "enciende la tv", "activar televisor", "prender tv"],
            "tv_off": ["apagar la tele", "apaga la tv", "suspender televisor", "apagar tv"],
            "tv_volume_up": ["sube el volumen", "subir volumen", "más volumen"],
            "tv_volume_down": ["baja el volumen", "bajar volumen", "menos volumen"],
            "tv_mute": ["silenciar tv", "silencio tv", "quitar sonido"],
            "tv_set_volume": ["pon el volumen en", "poner volumen a", "volumen a"],
            "tv_set_channel": ["pon el canal", "cambiar al canal", "ver el canal"],
            "tv_list_apps": ["qué aplicaciones tiene", "lista de apps"],
            "tv_set_input": ["pone el deco", "cambia a hdmi", "ver aire", "ver cable"]
        }

    def _get_helper_script(self, target_tv: Dict[str, Any], action: str) -> Optional[str]:
        """Localiza dinámicamente el script controlador basado en el modelo del dispositivo"""
        model_type: str = str(target_tv.get("type", "android")).lower()
        folder: str = "sei800tc1" if any(x in model_type for x in ["deco", "sei8"]) else "tcl32s60a"
        
        filename: str = f"{action}.py"
        # Adaptación de prefijos para modelos específicos (Deco)
        if folder == "sei800tc1" and action.startswith("tv_"):
            candidate = action.replace("tv_", "deco_") + ".py"
            if os.path.exists(os.path.join(self.plugin_dir, folder, candidate)):
                filename = candidate

        paths: List[str] = [
            os.path.join(self.plugin_dir, folder, filename),
            os.path.join(self.plugin_dir, filename)
        ]
        
        for p in paths:
            if os.path.exists(p):
                return p
        return None

    def handle_intent(self, intent_name: str, command: str, **kwargs: Any) -> Optional[str]:
        """Despachador central de lógica de ejecución"""
        target: Optional[Dict[str, Any]] = self._resolve_target_tv(command, intent_name)
        if not target:
            return "No se pudo identificar una TV configurada para esta acción."

        target_ip: str = str(target.get("ip", ""))
        
        # Acciones directas vía ADB para optimizar latencia
        if intent_name == "tv_volume_up":
            subprocess.Popen(["adb", "-s", f"{target_ip}:5555", "shell", "input", "keyevent", "24"]) # type: ignore
            return "Volumen incrementado."
        elif intent_name == "tv_volume_down":
            subprocess.Popen(["adb", "-s", f"{target_ip}:5555", "shell", "input", "keyevent", "25"]) # type: ignore
            return "Volumen disminuido."
        elif intent_name == "tv_mute":
            subprocess.Popen(["adb", "-s", f"{target_ip}:5555", "shell", "input", "keyevent", "164"]) # type: ignore
            return "Silenciado."
        
        # Acciones complejas vía scripts externos
        if intent_name == "tv_on":
            return self._run_script(target, "tv_on", ["--ip", target_ip])
        elif intent_name == "tv_off":
            return self._run_script(target, "tv_off", ["--ip", target_ip])
        elif intent_name == "tv_set_channel":
            import re
            match = re.search(r'(?:canal|el)\s+(\w+)', command.lower())
            channel: str = match.group(1) if match else command.split()[-1]
            return self._run_script(target, "set_channel", ["--ip", target_ip, "--channel", channel])
        elif intent_name == "tv_set_input":
            script_name: str = "set_input_deco" if any(x in command.lower() for x in ["deco", "hdmi"]) else "tv_input"
            return self._run_script(target, script_name, ["--ip", target_ip])
        
        return None

    def _run_script(self, target: Dict[str, Any], action: str, args: List[str]) -> str:
        """Ejecuta controladores especializados de forma asíncrona"""
        script_path: Optional[str] = self._get_helper_script(target, action)
        if script_path:
            subprocess.Popen(["python3", script_path] + args) # type: ignore
            label: str = str(target.get("name", target.get("room", "televisor")))
            return f"Ejecutando {action} en {label}."
        return f"Controlador {action} no disponible para este modelo."

    # Métodos de retrocompatibilidad
    def turn_on(self, target: Dict[str, Any]) -> str: return self._run_script(target, "tv_on", ["--ip", str(target.get("ip"))])
    def turn_off(self, target: Dict[str, Any]) -> str: return self._run_script(target, "tv_off", ["--ip", str(target.get("ip"))])
    def volume_up(self, target: Dict[str, Any]) -> str: return self.handle_intent("tv_volume_up", "") # type: ignore
    def volume_down(self, target: Dict[str, Any]) -> str: return self.handle_intent("tv_volume_down", "") # type: ignore
    def mute(self, target: Dict[str, Any]) -> str: return self.handle_intent("tv_mute", "") # type: ignore
    def set_volume(self, target: Dict[str, Any], level: int) -> str: return self._run_script(target, "tv_set_volume", ["--ip", str(target.get("ip")), "--level", str(level)])
    def set_channel(self, target: Dict[str, Any], channel: str) -> str: return self._run_script(target, "set_channel", ["--ip", str(target.get("ip")), "--channel", channel])
    def scan_channels(self, target: Dict[str, Any]) -> str: return self._run_script(target, "scan_ultra_fast", ["--ip", str(target.get("ip"))])
    def update_app_list(self, target: Dict[str, Any]) -> str: return self._run_script(target, "list_tv_apps", ["--ip", str(target.get("ip"))])
    def set_input_tv(self, target: Dict[str, Any]) -> str: return self._run_script(target, "tv_input", ["--ip", str(target.get("ip"))])
    def set_input_deco(self, target: Dict[str, Any]) -> str: return self._run_script(target, "set_input_deco", ["--ip", str(target.get("ip"))])
    
    def _get_tv_label(self, tv: Dict[str, Any]) -> str:
        """Etiqueta amigable para la TV"""
        name: Optional[str] = tv.get("name")
        room: Optional[str] = tv.get("room")
        if name: return name
        if room: return f"tele del {room}"
        return "televisión"
