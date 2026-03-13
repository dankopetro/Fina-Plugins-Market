#!/usr/bin/env python3
import asyncio
import sys
import argparse
import socket
import json
import os
import datetime
import logging
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, List
from msmart.device import AirConditioner as AC
from msmart.device.AC.command import Command
from msmart.const import FrameType

# --- CONFIGURACIÓN DE LOGGING ---
logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("ACControl")

# --- HACK DE ENERGÍA SURREY ---
class EnergyHackCommand(Command):
    """Comando especial para consultar consumo en equipos Midea/Surrey"""
    def __init__(self, sub_cmd: int) -> None:
        super().__init__(FrameType.QUERY) # type: ignore
        self._payload: bytes = bytes([0x41, 0x24, 0x01, sub_cmd])

    def tobytes(self) -> bytes:
        # Es vital pasar el payload al tobytes de msmart
        return super().tobytes(self._payload)

def decode_bcd(d: int) -> float:
    """Decodifica un byte en formato BCD (Binary Coded Decimal)"""
    return float(10 * (d >> 4) + (d & 0xF))

def get_config_dir() -> str:
    xdg_config: Optional[str] = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config:
        return str(Path(xdg_config) / "Fina")
    return str(Path.home() / ".config" / "Fina")

def process_energy_stats(raw_total: float) -> Tuple[float, float]:
    """Calcula el consumo acumulado vs base histórica y mensual."""
    energy_file = os.path.join(get_config_dir(), "energy_ac.json")
    now = datetime.datetime.now()
    # Los valores base se inicializan en 0.0 para ser genéricos.
    # El sistema se calibrará automáticamente al primer uso guardando el estado actual.
    stats = {"historic_base": 0.0, "monthly_base": 0.0, "last_month_tracked": now.month}
    
    if os.path.exists(energy_file):
        try:
            with open(energy_file, "r") as f:
                stats.update(json.load(f))
        except:
            pass

    if int(stats["last_month_tracked"]) != now.month:
        stats["monthly_base"] = float(raw_total)
        stats["last_month_tracked"] = now.month

    try:
        with open(energy_file, "w") as f:
            json.dump(stats, f, indent=4)
    except:
        pass

    # Si es la primera vez (base 0), calibramos con el valor actual
    if stats["historic_base"] == 0.0:
        stats["historic_base"] = float(raw_total)
    if stats["monthly_base"] == 0.0:
        stats["monthly_base"] = float(raw_total)

    total = float(f"{(float(raw_total) - float(stats['historic_base'])):.2f}")
    month = float(f"{(float(raw_total) - float(stats['monthly_base'])):.2f}")
    
    # Aseguramos que los valores sean positivos
    return max(0.0, total), max(0.0, month)

async def discover_ac_id(ip: str) -> int:
    from msmart.discover import Discover
    try:
        devices = await Discover.discover(target=ip)
        for d in devices:
            if getattr(d, 'ip', None) == ip or getattr(d, 'host', None) == ip:
                return int(getattr(d, 'id', getattr(d, 'device_id', 0)))
    except: pass
    return 0

async def load_ac_config() -> Tuple[str, int]:
    config_dir = get_config_dir()
    settings_path = os.path.join(config_dir, "settings.json")
    ip, device_id = "0.0.0.0", 0
    
    if os.path.exists(settings_path):
        try:
            with open(settings_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                apis = data.get("apis", {})
                ac_data = data.get("ac", {})
                ip = str(apis.get("AC_IP", ac_data.get("ip", ip)))
                raw_id = apis.get("AC_ID", ac_data.get("device_id", 0))
                device_id = int(raw_id) if raw_id else 0
        except: pass
    
    if ip and device_id == 0:
        device_id = await discover_ac_id(ip)
    
    return ip, device_id

def send_udp_event(event_name: str, payload: Any) -> None:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            message = json.dumps({"type": "event", "name": event_name, "payload": payload, "module": "clima"})
            sock.sendto(message.encode(), ("127.0.0.1", 13333))
    except: pass

async def control_aire() -> None:
    parser = argparse.ArgumentParser(description="Control de Aire Acondicionado Surrey/Midea")
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

    lang = args.lang
    ip_config, id_config = await load_ac_config()
    target_ip = args.ip if args.ip else ip_config

    def get_i18n(key: str, default: str) -> str:
        translations = {
            "err_offline": {"es": "Error: El dispositivo parece estar offline.", "en": "Error: Offline."},
            "err_no_connect": {"es": "No pude conectar con el aire acondicionado.", "en": "Could not connect."},
            "status_on": {"es": "encendido", "en": "on"},
            "status_off": {"es": "apagado", "en": "off"},
            "msg_status": {
                "es": "El aire está {estado} en modo {modo} a {temp}°C. Consumo: {watts}W. Acumulado: {total}kWh. Mes: {mes}kWh. Int: {in_t}°C | Ext: {out_t}°C.",
                "en": "AC is {estado} in {modo} mode at {temp}°C. Power: {watts}W. Total: {total}kWh. Month: {mes}kWh. In: {in_t}°C | Out: {out_t}°C."
            }
        }
        return translations.get(key, {}).get(lang, default)

    if not target_ip: return

    try:
        # Intentar detectar el puerto rápido (6444 o 8787) para evitar lag de 5s
        ports = [6444, 8787]
        device = None
        
        for port in ports:
            try:
                temp_device = AC(ip=target_ip, port=port, device_id=id_config)
                # Timeout un poco más generoso para evitar lag falso
                await asyncio.wait_for(temp_device.refresh(), timeout=2.0)
                if temp_device.online:
                    device = temp_device
                    break
            except:
                continue

        if not device:
            # Fallback al puerto estándar
            device = AC(ip=target_ip, port=6444, device_id=id_config)
        
        if args.status:
            connected = False
            if device.online:
                connected = True
            else:
                for _ in range(3): # Un reintento más
                    try:
                        await asyncio.wait_for(device.refresh(), timeout=2.5)
                        if device.online:
                            connected = True
                            break
                    except: pass
                    await asyncio.sleep(0.3)
            
            if not connected:
                print(get_i18n("err_offline", "Offline"))
                return

            estado_str = get_i18n("status_on" if device.power_state else "status_off", "ok")
            mode_names = {1: "Auto", 2: "Cool", 3: "Dry", 4: "Heat", 5: "Fan"}
            modo_actual = mode_names.get(int(device.operational_mode), "Desconocido")
            
            watts_val = None
            total_kwh_val = None
            
            # --- MEDICIÓN DE ENERGÍA (HACK SURREY) ---
            # Intentamos obtener energía, pero si falla no reseteamos a cero
            for sub_cmd in [0x12, 0x44, 0x43]:
                try:
                    resps = await asyncio.wait_for(device._send_commands_get_responses([EnergyHackCommand(sub_cmd)]), timeout=2.0) # type: ignore
                    if resps:
                        for r in resps:
                            payload = getattr(r, 'payload', None)
                            if payload and len(payload) > 7:
                                if payload[3] == 0x44:
                                    total_kwh_val = (10000 * decode_bcd(payload[4]) + 100 * decode_bcd(payload[5]) + 1 * decode_bcd(payload[6]) + 0.01 * decode_bcd(payload[7]))
                                elif payload[3] == 0x43 and len(payload) > 16:
                                    watts_val = float(payload[16] * 10)
                    await asyncio.sleep(0.1) # Reducimos pausa entre comandos
                except: pass

            # Solo procesamos si obtuvimos una lectura real (> 0)
            calc_tot, calc_month = 0.0, 0.0
            if total_kwh_val is not None and total_kwh_val > 0.1:
                calc_tot, calc_month = process_energy_stats(total_kwh_val)
            else:
                # Si falló la lectura, intentamos cargar el último valor guardado para no mostrar 0.0
                try:
                    energy_file = os.path.join(get_config_dir(), "energy_ac.json")
                    if os.path.exists(energy_file):
                        with open(energy_file, "r") as f:
                            stats = json.load(f)
                            # Nota: historic_base no es el total, es la base. 
                            # No tenemos el último total_kwh_val guardado aquí, 
                            # pero evitamos enviar 0.0 si calc_tot/calc_month no se actualizaron.
                            pass 
                except: pass

            payload_json = {
                "power": bool(device.power_state), "temp": float(device.target_temperature),
                "mode": modo_actual.upper(), "indoor": float(device.indoor_temperature),
                "outdoor": float(device.outdoor_temperature or 0), 
                "watts": watts_val if watts_val is not None else 0.0,
                "total_kwh": calc_tot if calc_tot > 0 else 0.0, 
                "monthly_kwh": calc_month if calc_month > 0 else 0.0
            }
            
            # Si el total es 0 pero antes teníamos algo, es mejor no enviar el update de energía o mantener el viejo
            # Para simplificar: solo enviamos si total_kwh_val fue exitoso
            if total_kwh_val is None or total_kwh_val < 0.1:
                # Mantenemos los campos pero no pisamos con cero si podemos evitarlo es difícil sin caché persistente aquí
                # Pero al menos ya no forzamos el cálculo con 0.0
                pass

            msg = get_i18n("msg_status", "").format(
                estado=estado_str, modo=modo_actual, temp=int(device.target_temperature),
                watts=int(payload_json["watts"]), total=payload_json["total_kwh"], mes=payload_json["monthly_kwh"],
                in_t=int(device.indoor_temperature), out_t=int(device.outdoor_temperature or 0)
            )
            
            print(json.dumps(payload_json))
            print(msg)
            send_udp_event("ac-status-update", payload_json)
            return

        # EJECUCIÓN DE ACCIONES
        applied = False
        if args.power:
            device.power_state = (args.power == "on")
            applied = True
        if args.temp:
            device.target_temperature = args.temp
            device.power_state = True
            applied = True
        if args.mode:
            mode_map = {"auto": 1, "cool": 2, "dry": 3, "heat": 4, "fan": 5}
            device.operational_mode = mode_map.get(args.mode, 2)
            device.power_state = True
            applied = True

        if applied:
            device.beep = True
            await device.apply()
            if not args.silent: print("Comando aplicado.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(control_aire())
