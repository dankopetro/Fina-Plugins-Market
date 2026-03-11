#!/usr/bin/env python3
import asyncio
import sys
import argparse
import socket
import json
import os
import logging
from pathlib import Path
from typing import Optional, Any, Dict, List, Tuple, Union, cast
from msmart.device import AirConditioner as AC # type: ignore
from msmart.device.AC.command import Command # type: ignore
from msmart.const import FrameType # type: ignore
import datetime

# Configuración de logging (Cambiado a WARNING para salida limpia)
logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("ACControl")

# --- HACK DE ENERGÍA SURREY ---
class EnergyHackCommand(Command):
    """Comando especial para consultar consumo en equipos Midea/Surrey"""
    def __init__(self, sub_cmd: int) -> None:
        super().__init__(FrameType.QUERY) # type: ignore
        self._payload: bytearray = bytearray([0x41, 0x24, 0x01, sub_cmd])

    def tobytes(self) -> bytes:
        p: bytearray = bytearray(20)
        p[0:4] = self._payload # type: ignore
        return super().tobytes(p) # type: ignore

def decode_bcd(d: int) -> float:
    """Decodifica un byte en formato BCD (Binary Coded Decimal)"""
    return float(10 * (d >> 4) + (d & 0xF))
# ------------------------------

def get_energy_file() -> str:
    """Retorna la ruta del archivo de persistencia energética"""
    return os.path.join(get_config_dir(), "energy_ac.json")

def process_energy_stats(raw_total: float) -> Tuple[float, float]:
    """
    Calcula el consumo acumulado vs base histórica y mensual.
    Maneja el reseteo automático el día 1 de cada mes.
    """
    energy_file = get_energy_file()
    now = datetime.datetime.now()
    
    # Valores por defecto (según pedido de Claudio)
    stats: Dict[str, Union[float, int]] = {
        "historic_base": 4960.0,
        "monthly_base": 5014.32, # Base de Ergen hoy 9 de Marzo
        "last_month_tracked": now.month
    }

    # Cargar persistencia si existe
    if os.path.exists(energy_file):
        try:
            with open(energy_file, "r") as f:
                stats.update(json.load(f))
        except Exception as e:
            logger.warning(f"No se pudo leer energy_ac.json, usando defaults: {e}")

    # Lógica de Reseteo Mensual (Día 1)
    if int(stats["last_month_tracked"]) != now.month:
        logger.info(f"📅 Cambio de mes detectado ({stats['last_month_tracked']} -> {now.month}). Reseteando base mensual.")
        stats["monthly_base"] = float(raw_total)
        stats["last_month_tracked"] = now.month

    # Guardar cambios
    try:
        with open(energy_file, "w") as f:
            json.dump(stats, f, indent=4)
    except Exception as e:
        logger.error(f"Error guardando energy_ac.json: {e}")

    # Cálculos
    if raw_total <= 0:
        # Si la lectura falló, mantenemos los valores en 0 pero no por error de cálculo
        return 0.0, 0.0

    total_since_feb = float(f"{(float(raw_total) - float(stats['historic_base'])):.2f}")
    current_month_usage = float(f"{(float(raw_total) - float(stats['monthly_base'])):.2f}")
    
    return max(0.0, total_since_feb), max(0.0, current_month_usage)

# ------------------------------

def get_config_dir() -> str:
    """Obtiene el directorio de configuración de Fina siguiendo estándares XDG"""
    xdg_config: Optional[str] = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config:
        return str(Path(xdg_config) / "Fina")
    return str(Path.home() / ".config" / "Fina")

def find_project_root() -> Optional[str]:
    """Busca la raíz del proyecto basándose en marcadores conocidos"""
    curr: Path = Path(__file__).resolve().parent
    for parent in [curr] + list(curr.parents):
        if (parent / "package.json").exists() or (parent / "src" / "App.vue").exists():
            return str(parent)
    return None

async def discover_ac_id(ip: str) -> int:
    """Busca el ID de un dispositivo Midea/Surrey de forma dinámica y robusta"""
    from msmart.discover import Discover # type: ignore
    logger.info(f"🔍 Intentando autodescubrimiento en {ip}...")
    
    # 1. Escaneo dirigido (Más fiable, evita bugs de broadcast en algunas redes)
    try:
        devices = await Discover.discover(target=ip)
        for d in devices:
            if getattr(d, 'ip', None) == ip or getattr(d, 'host', None) == ip:
                obj_id = getattr(d, 'id', getattr(d, 'device_id', 0))
                logger.info(f"✅ ID encontrado (Dirigido): {obj_id}")
                return int(obj_id)
    except Exception as e:
        logger.debug(f"Aviso: Fallo en escaneo dirigido: {e}")

    # 2. Escaneo Broadcast (Backup si la IP cambió o no responde directo)
    try:
        devices = await Discover.discover()
        for d in devices:
            if getattr(d, 'ip', None) == ip or getattr(d, 'host', None) == ip:
                obj_id = getattr(d, 'id', getattr(d, 'device_id', 0))
                logger.info(f"✅ ID encontrado (Broadcast): {obj_id}")
                return int(obj_id)
    except Exception as e:
        logger.warning(f"Error en autodescubrimiento general: {e}")
    
    return 0

async def load_ac_config() -> Tuple[str, int]:
    """Carga IP e ID del AC desde settings.json con autodescubrimiento de respaldo"""
    config_dir: str = get_config_dir()
    proj_root: Optional[str] = find_project_root()
    
    ip: str = ""
    device_id: int = 0
    
    candidates: List[Optional[str]] = [
        os.path.join(config_dir, "settings.json"),
        os.path.join(proj_root, "config", "settings.json") if proj_root else None
    ]
    
    for path in candidates:
        if path and os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data: Dict[str, Any] = json.load(f)
                    apis: Dict[str, Any] = data.get("apis", {})
                    ac_data: Dict[str, Any] = data.get("ac", {})
                    
                    ip = str(apis.get("AC_IP", ac_data.get("ip", "")))
                    raw_id = apis.get("AC_ID", ac_data.get("device_id", 0))
                    try:
                        device_id = int(raw_id) if raw_id else 0
                    except ValueError:
                        device_id = 0
                    
                    if ip:
                        # Si tenemos IP pero no ID, intentamos descubrirlo una vez
                        if device_id == 0:
                            device_id = await discover_ac_id(ip)
                        return ip, device_id
            except Exception as e:
                logger.warning(f"Error leyendo configuración en {path}: {e}")
                
    return ip, device_id

def send_udp_event(event_name: str, payload: Any) -> None:
    """Envía un evento UDP al Brain de Fina de forma segura"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            message: str = json.dumps({
                "type": "event", 
                "name": event_name, 
                "payload": payload, 
                "module": "clima"
            })
            sock.sendto(message.encode(), ("127.0.0.1", 13333))
    except Exception as e:
        logger.error(f"Error enviando evento UDP: {e}")

async def control_aire() -> None:
    """Manejador principal de control de aire acondicionado Midea/Surrey"""
    parser = argparse.ArgumentParser(description="Control de Aire Acondicionado Midea/Surrey")
    parser.add_argument("--power", choices=["on", "off"])
    parser.add_argument("--temp", type=float)
    parser.add_argument("--swing", choices=["on", "off"])
    parser.add_argument("--turbo", choices=["on", "off"])
    parser.add_argument("--mode", choices=["auto", "cool", "dry", "heat", "fan"])
    parser.add_argument("--fan", choices=["auto", "low", "medium", "high", "full"])
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--silent", action="store_true")
    parser.add_argument("--ip", type=str)
    parser.add_argument("--lang", type=str, default="es")
    args = parser.parse_args()

    lang: str = args.lang
    ip_config, id_config = await load_ac_config()
    target_ip: str = cast(str, args.ip) if args.ip else ip_config

    def get_i18n(key: str, default: str) -> str:
        translations: Dict[str, Dict[str, str]] = {
            "err_offline": {"es": "Error: El dispositivo parece estar offline.", "en": "Error: Device is offline."},
            "err_no_connect": {"es": "No pude conectar con el aire acondicionado.", "en": "Could not connect to AC."},
            "status_on": {"es": "encendido", "en": "on"},
            "status_off": {"es": "apagado", "en": "off"},
            "mode_unknown": {"es": "Desconocido", "en": "Unknown"},
            "msg_status": {
                "es": "El aire está {estado} en modo {modo} a {temp}°C. Consumo: {watts}W. Acumulado: {total}kWh. Mes: {mes}kWh. Int: {in_t}°C | Ext: {out_t}°C.",
                "en": "AC is {estado} in {modo} mode at {temp}°C. Power: {watts}W. Total: {total}kWh. Month: {mes}kWh. In: {in_t}°C | Out: {out_t}°C."
            },
            "msg_hum": {"es": " Humedad: {h}%", "en": " Humidity: {h}%"},
            "msg_ac_power": {"es": "Aire acondicionado {estado}.", "en": "AC {estado}."},
            "msg_ac_temp": {"es": "Aire a {t} grados.", "en": "AC set to {t} degrees."},
            "msg_ac_range": {"es": "Temperatura fuera de rango (17-30).", "en": "Temperature out of range."},
            "msg_ac_mode": {"es": "Modo {m} activado.", "en": "Mode {m} activated."},
            "msg_ac_fan": {"es": "Ventilador en {f}.", "en": "Fan set to {f}."},
            "msg_ac_swing": {"es": "Swing {s}.", "en": "Swing {s}."},
            "msg_ac_turbo": {"es": "Turbo {s}.", "en": "Turbo {s}."},
            "val_enabled": {"es": "activado", "en": "enabled"},
            "val_disabled": {"es": "desactivado", "en": "disabled"},
        }
        return translations.get(key, {}).get(lang, default)

    if not target_ip:
        logger.error("✗ No se detectó IP del AC. Abortando.")
        return

    try:
        device: Any = AC(ip=target_ip, port=6444, device_id=id_config) # type: ignore
        
        if args.status:
            # Reintentos para robustez en redes inestables
            connected: bool = False
            for _ in range(3):
                try:
                    await device.refresh() # type: ignore
                    if device.online: # type: ignore
                        connected = True
                        break
                except Exception:
                    pass
                await asyncio.sleep(1)
            
            if not connected:
                print(get_i18n("err_offline", "Error: Offline"))
                if not args.silent:
                    send_udp_event("fina-speak", get_i18n("err_no_connect", "No pude conectar"))
                return

            estado_str: str = get_i18n("status_on" if device.power_state else "status_off", "encendido") # type: ignore
            mode_names: Dict[int, str] = {1: "Auto", 2: "Cool", 3: "Dry", 4: "Heat", 5: "Fan"}
            modo_actual: str = mode_names.get(int(device.operational_mode), "Desconocido") # type: ignore
            
            # --- MEDICIÓN DE ENERGÍA (RE-IMPLEMENTADA POR CLAUDIO) ---
            watts_val: float = 0.0
            total_kwh_val: float = 0.0
            
            try:
                # 1. ENERGÍA: Búsqueda dinámica en buffers de Midea/Surrey
                for hack in [0x12, 0x44, 0x43]:
                    try:
                        resps = await device._send_commands_get_responses([EnergyHackCommand(hack)]) # type: ignore
                        if resps:
                            for r in resps:
                                if getattr(r, 'id', None) in [0xC0, 0xC1] and hasattr(r, 'payload'):
                                    d: bytearray = r.payload
                                    if len(d) >= 8:
                                        if d[3] == 0x44:
                                            total_kwh_val = (10000 * decode_bcd(d[4]) + 100 * decode_bcd(d[5]) + 1 * decode_bcd(d[6]) + 0.01 * decode_bcd(d[7]))
                                        elif d[3] == 0x43 and len(d) > 16:
                                            raw_w = int(d[16])
                                            if raw_w > 0:
                                                watts_val = float(raw_w * 10)
                        await asyncio.sleep(0.3) # Pausa para no saturar al dispositivo
                    except Exception:
                        pass
            except Exception as energy_err:
                logger.debug(f"Error obteniendo energía: {energy_err}")

            # --- CÁLCULO DE CONSUMO PERSONALIZADO Ergen ---
            calc_tot, calc_month = process_energy_stats(total_kwh_val)

            msg: str = get_i18n("msg_status", "").format(
                estado=estado_str, 
                modo=modo_actual, 
                temp=int(device.target_temperature), # type: ignore
                watts=int(watts_val), 
                total=calc_tot, 
                mes=calc_month,
                in_t=int(device.indoor_temperature), # type: ignore
                out_t=int(device.outdoor_temperature or 0) # type: ignore
            )
            if device.indoor_humidity: # type: ignore
                msg += get_i18n("msg_hum", " Humedad: {h}%").format(h=device.indoor_humidity) # type: ignore
            
            # Notificar al Brain
            send_udp_event("ac-status-update", {
                "power": bool(device.power_state), # type: ignore
                "temp": float(device.target_temperature), # type: ignore
                "mode": modo_actual.upper(),
                "indoor": float(device.indoor_temperature), # type: ignore
                "outdoor": float(device.outdoor_temperature or 0), # type: ignore
                "watts": watts_val,
                "total_kwh": calc_tot,
                "monthly_kwh": calc_month,
                "raw_total": float(f"{float(total_kwh_val):.2f}")
            })
            
            # Imprimir JSON para que el panel de Fina lo parsee de forma fiable
            payload = {
                "power": bool(device.power_state),
                "temp": float(device.target_temperature),
                "mode": modo_actual.upper(),
                "indoor": float(device.indoor_temperature),
                "outdoor": float(device.outdoor_temperature or 0),
                "watts": watts_val,
                "total_kwh": calc_tot,
                "monthly_kwh": calc_month
            }
            print(json.dumps(payload))
            
            # PARCHE FINA: Línea de datos puros protegida
            print(f"FINA_AC_DATA|{payload['power']}|{payload['temp']}|{payload['mode']}|{payload['indoor']}|{payload['outdoor']}|{payload['watts']}|{payload['total_kwh']}|{payload['monthly_kwh']}")

            
            # Solo imprimimos texto humano si NO estamos en modo silencioso (para depuración manual)
            if not args.silent:
                print(msg)

            return

        # EJECUCIÓN DE ACCIONES
        applied: bool = False
        action_msg: str = ""
        
        if args.power:
            device.power_state = (args.power == "on") # type: ignore
            applied = True
            action_msg = get_i18n("msg_ac_power", "").format(estado=get_i18n("status_on" if device.power_state else "status_off", "ok")) # type: ignore

        if args.temp:
            if 17 <= args.temp <= 30:
                device.target_temperature = args.temp # type: ignore
                device.power_state = True # type: ignore
                applied = True
                if not action_msg: 
                    action_msg = get_i18n("msg_ac_temp", "").format(t=args.temp)
            else:
                print(get_i18n("msg_ac_range", "Error: Rango"))

        if args.mode:
            mode_map: Dict[str, int] = {"auto": 1, "cool": 2, "dry": 3, "heat": 4, "fan": 5}
            device.operational_mode = mode_map.get(args.mode, 2) # type: ignore
            device.power_state = True # type: ignore
            applied = True
            if not action_msg: 
                action_msg = get_i18n("msg_ac_mode", "").format(m=args.mode)

        if args.fan:
            speeds: Dict[str, int] = {"auto": 102, "low": 40, "medium": 60, "high": 80, "full": 100}
            device.fan_speed = speeds.get(args.fan, 102) # type: ignore
            applied = True
            if not action_msg: 
                action_msg = get_i18n("msg_ac_fan", "").format(f=args.fan)

        if args.swing:
            device.swing_mode = 0x0C if args.swing == "on" else 0x00 # type: ignore
            applied = True
            val_s: str = get_i18n("val_enabled" if args.swing == "on" else "val_disabled", "ok")
            if not action_msg: 
                action_msg = get_i18n("msg_ac_swing", "").format(s=val_s)

        if args.turbo:
            device.turbo = (args.turbo == "on") # type: ignore
            applied = True
            val_t: str = get_i18n("val_enabled" if args.turbo == "on" else "val_disabled", "ok")
            if not action_msg: 
                action_msg = get_i18n("msg_ac_turbo", "").format(s=val_t)

        if applied:
            device.beep = True # type: ignore
            await device.apply() # type: ignore
            print(action_msg)
            if not args.silent and action_msg:
                send_udp_event("fina-speak", action_msg)

    except Exception as e:
        logger.error(f"Error controlando el aire acondicionado: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(control_aire())
    except KeyboardInterrupt:
        pass
    except Exception as fatal:
        logger.critical(f"✗ Fatal: {fatal}")
        sys.exit(1)
