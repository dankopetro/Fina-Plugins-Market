#!/usr/bin/env python3
import os
import subprocess
import json
import logging
import threading
import time
from pathlib import Path
from typing import Optional, Dict, Any, List

# ==================================================================================================
# CLASE PRINCIPAL DEL PLUGIN (Telecentro SEI800TC1 / Android TV)
# ==================================================================================================
class DecoPlugin:
    """Plugin para control de Televisores y Decodificadores Android TV vía ADB"""
    
    def __init__(self, context: Any) -> None:
        self.context: Any = context
        self.logger: logging.Logger = logging.getLogger("DecoPlugin")
        self.plugin_dir: str = os.path.dirname(os.path.abspath(__file__))
        self.settings: Dict[str, Any] = self._load_settings()
        self.logger.info("📺 TV Plugin (Android TV/Deco) Inicializado")
        self._start_keepalive()  # Anti-standby en background
        
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
        """Carga configuración desde múltiples ubicaciones posibles"""
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

    # ──────────────────────────────────────────────────────────────
    # KEEPALIVE ANTI-STANDBY
    # ──────────────────────────────────────────────────────────────
    def _start_keepalive(self) -> None:
        """
        Lanza el hilo de keepalive anti-standby.
        Activo por defecto (30 min) para todos los dispositivos configurados.
        Solo se desactiva si el usuario define explícitamente keepalive_interval_min: 0.
        """
        tvs_raw: Any = self.settings.get("tvs", [])
        tvs: List[Dict[str, Any]] = list(tvs_raw.values()) if isinstance(tvs_raw, dict) else tvs_raw

        # Activo si hay al menos un dispositivo con intervalo > 0 (default = 30)
        has_keepalive: bool = any(
            int(tv.get("keepalive_interval_min", 30)) > 0  # 30 min por defecto
            for tv in tvs if isinstance(tv, dict)
        )
        if not has_keepalive:
            return

        t: threading.Thread = threading.Thread(
            target=self._keepalive_loop,
            daemon=True,
            name="DecoKeepalive"
        )
        t.start()
        self.logger.info("⏱️ Keepalive anti-standby activo (30 min por defecto).")

    def _keepalive_loop(self) -> None:
        """
        Bucle daemon: cada N minutos por dispositivo, envía
        KEYCODE_CAPTIONS (tecla CC — silente visualmente) por ADB
        para resetear el timer de inactividad del deco.
        """
        # Tabla de último ping por IP
        last_ping: Dict[str, float] = {}

        while True:
            time.sleep(60)  # Chequeo cada 1 minuto
            try:
                # Recargar settings para detectar cambios en caliente
                self.settings = self._load_settings()
                tvs_raw: Any = self.settings.get("tvs", [])
                tvs: List[Dict[str, Any]] = list(tvs_raw.values()) if isinstance(tvs_raw, dict) else tvs_raw

                for tv in tvs:
                    if not isinstance(tv, dict):
                        continue
                    # Default 30 min si no está definido, 0 = desactivado explícitamente
                    interval_min: int = int(tv.get("keepalive_interval_min", 30))
                    if interval_min <= 0:
                        continue

                    ip: str = str(tv.get("ip", ""))
                    if not ip:
                        continue

                    now: float = time.time()
                    elapsed_min: float = (now - last_ping.get(ip, 0)) / 60.0

                    if elapsed_min >= interval_min:
                        # Verificar que el deco esté encendido antes de pinear
                        if self._is_screen_active(ip):
                            try:
                                subprocess.run(
                                    ["adb", "-s", f"{ip}:5555", "shell",
                                     "input", "keyevent", "175"],  # KEYCODE_CAPTIONS
                                    capture_output=True, timeout=3
                                ) # type: ignore
                                last_ping[ip] = now
                                name: str = str(tv.get("name", ip))
                                self.logger.debug(f"⏱️ Keepalive enviado → {name} ({ip})")
                            except Exception as e:
                                self.logger.warning(f"⚠️ Keepalive falló en {ip}: {e}")
                        else:
                            # Pantalla apagada, resetear timer para no acumular
                            last_ping[ip] = now
            except Exception as loop_err:
                self.logger.error(f"Error en keepalive loop: {loop_err}")

    def _ensure_adb_connections(self) -> None:
        """Asegura que todos los dispositivos configurados estén conectados vía ADB"""
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
                    subprocess.run(["adb", "connect", f"{ip}:5555"], capture_output=True, timeout=2.0) # type: ignore
                except Exception:
                    pass

    def _verify_connection(self, ip: str) -> bool:
        """Verifica la salud de la conexión ADB y limpia sesiones muertas"""
        try:
            subprocess.run(["adb", "-s", f"{ip}:5555", "shell", "echo", "1"], 
                           capture_output=True, timeout=1.5, check=True) # type: ignore
            return True
        except Exception:
            subprocess.run(["adb", "disconnect", f"{ip}:5555"], capture_output=True) # type: ignore
            return False

    def _is_screen_active(self, ip: str) -> bool:
        """Determina si la pantalla del dispositivo está encendida"""
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
        """Resuelve qué televisor/deco debe recibir el comando"""
        tvs_data: Any = self.settings.get("tvs", [])
        tvs_list: List[Dict[str, Any]] = []
        
        if isinstance(tvs_data, dict):
            tvs_list = [{"name": k, **v} for k, v in tvs_data.items() if isinstance(v, dict)]
        elif isinstance(tvs_data, list):
            tvs_list = tvs_data
        
        query_low: str = query.lower()

        # 1. Mención explícita (Nombre o Habitación)
        for tv in tvs_list:
            name: str = str(tv.get("name", "")).lower()
            room: str = str(tv.get("room", "")).lower()
            if (name and name in query_low) or (room and room in query_low):
                return tv
            if room == "deco" and any(x in query_low for x in ["decodificador", "el deco", "deco"]):
                return tv

        # 2. Resolución por estado activo
        if intent != "deco_on":
            active_ips: List[str] = self._get_active_ips()
            candidates: List[Dict[str, Any]] = [tv for tv in tvs_list if tv.get("ip") in active_ips]
            if len(candidates) == 1:
                return candidates[0]

        # 3. Fallback: Primera TV habilitada
        for tv in tvs_list:
            if tv.get("enabled", True):
                return tv
        
        return tvs_list[0] if tvs_list else None

    def get_intents(self) -> Dict[str, List[str]]:
        """Define los disparadores de lenguaje natural"""
        return {
            "deco_on": ["prender la tele", "enciende la tv", "prender tv", "activar televisor"],
            "deco_off": ["apagar la tele", "apaga la tv", "apagar tv", "apagar televisor"],
            "deco_volume_up": ["sube el volumen", "subir volumen", "más volumen"],
            "deco_volume_down": ["baja el volumen", "bajar volumen", "menos volumen"],
            "deco_mute": ["silenciar tv", "silencio tv", "mute tv"],
            "deco_set_volume": ["pon el volumen en", "poner volumen a", "volumen a"],
            "deco_set_deco_channel": ["pon el canal", "cambiar al canal", "ver el canal"],
            "deco_list_apps": ["qué aplicaciones tiene", "lista de apps"],
            "deco_set_input": ["pone el deco", "cambia a hdmi", "ver aire"]
        }

    def _get_helper_script(self, target_tv: Dict[str, Any], action: str) -> Optional[str]:
        """Localiza el script específico para el modelo del dispositivo"""
        model: str = str(target_tv.get("type", "android")).lower()
        folder: str = "sei800tc1" if "deco" in model or "sei8" in model else "tcl32s60a"
        
        filename: str = f"{action}.py"
        # Mapeo especial para Deco
        if folder == "sei800tc1" and action.startswith("tv_"):
            filename = action.replace("tv_", "deco_") + ".py"
            if not os.path.exists(os.path.join(self.plugin_dir, folder, filename)):
                filename = action + ".py" # Reversión si no existe prefijo deco_

        paths: List[str] = [
            os.path.join(self.plugin_dir, folder, filename),
            os.path.join(self.plugin_dir, filename)
        ]
        
        for p in paths:
            if os.path.exists(p):
                return p
        return None

    def handle_intent(self, intent_name: str, command: str, **kwargs: Any) -> Optional[str]:
        """Despachador central de lógica para intents"""
        target: Optional[Dict[str, Any]] = self._resolve_target_tv(command, intent_name)
        if not target:
            return "No se encontró un dispositivo compatible configurado."

        target_ip: str = str(target.get("ip", ""))
        
        # Mapeo de acciones directas
        if intent_name == "deco_on":
            return self._run_script(target, "deco_on", ["--ip", target_ip])
        elif intent_name == "deco_off":
            return self._run_script(target, "deco_off", ["--ip", target_ip])
        elif intent_name == "deco_volume_up":
            subprocess.Popen(["adb", "-s", f"{target_ip}:5555", "shell", "input", "keyevent", "24"]) # type: ignore
            return "Volumen incrementado."
        elif intent_name == "deco_volume_down":
            subprocess.Popen(["adb", "-s", f"{target_ip}:5555", "shell", "input", "keyevent", "25"]) # type: ignore
            return "Volumen disminuido."
        elif intent_name == "deco_mute":
            subprocess.Popen(["adb", "-s", f"{target_ip}:5555", "shell", "input", "keyevent", "164"]) # type: ignore
            return "Silenciado."
        elif intent_name == "deco_set_deco_channel":
            import re
            match = re.search(r'(?:canal|el)\s+(\w+)', command.lower())
            channel: str = match.group(1) if match else command.split()[-1]
            return self._run_script(target, "set_deco_channel", ["--ip", target_ip, "--channel", channel])
        
        return None

    def _run_script(self, target: Dict[str, Any], action: str, args: List[str]) -> str:
        """Ejecuta un script auxiliar de forma asíncrona"""
        script_path: Optional[str] = self._get_helper_script(target, action)
        if script_path:
            subprocess.Popen(["python3", script_path] + args) # type: ignore
            label: str = str(target.get("name", target.get("room", "TV")))
            return f"Ejecutando {action} en {label}."
        return f"Controlador para {action} no disponible."

    # Métodos de compatibilidad con versiones anteriores del plugin
    def turn_on(self, target_tv: Dict[str, Any]) -> str: return self._run_script(target_tv, "deco_on", ["--ip", str(target_tv.get("ip"))])
    def turn_off(self, target_tv: Dict[str, Any]) -> str: return self._run_script(target_tv, "deco_off", ["--ip", str(target_tv.get("ip"))])
    def set_deco_channel(self, target_tv: Dict[str, Any], channel: str) -> str: return self._run_script(target_tv, "set_deco_channel", ["--ip", str(target_tv.get("ip")), "--channel", channel])
