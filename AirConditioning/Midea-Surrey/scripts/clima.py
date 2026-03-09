#!/usr/bin/env python3
"""
clima.py (scripts/ - Versión Standalone)
Script de control del Aire Acondicionado Surrey/Midea.
Versión autónoma sin dependencias del proyecto principal.
"""
import asyncio
import sys
import os
import argparse
import socket
import json
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from msmart.device import AirConditioner as AC # type: ignore
from msmart.device.AC.command import Command # type: ignore
from msmart.const import FrameType # type: ignore

# --- HACK DE ENERGÍA SURREY ---
class EnergyHackCommand(Command):
    """Comando especial para consultar consumo en equipos Midea/Surrey"""
    def __init__(self, sub_cmd: int) -> None:
        super().__init__(FrameType.QUERY) # type: ignore
        self._payload: bytes = bytes([0x41, 0x24, 0x01, sub_cmd])

    def tobytes(self) -> bytes:
        p: bytearray = bytearray(20)
        p[0:4] = self._payload # type: ignore
        return super().tobytes(p) # type: ignore

def decode_bcd(d: int) -> float:
    """Decodifica un byte en formato BCD (Binary Coded Decimal)"""
    return float(10 * (d >> 4) + (d & 0xF))
# ------------------------------

def get_config_dir() -> str:
    """Obtiene el directorio de configuración de Fina siguiendo estándares XDG"""
    xdg_config: Optional[str] = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config:
        return str(Path(xdg_config) / "Fina")
    return str(Path.home() / ".config" / "Fina")

def load_ac_config() -> Tuple[str, int]:
    """Carga IP e ID del AC desde settings.json (lee apis y ac)"""
    config_dir: str = get_config_dir()
    settings_path: str = os.path.join(config_dir, "settings.json")

    if os.path.exists(settings_path):
        try:
            with open(settings_path, "r", encoding="utf-8") as f:
                data: Dict[str, Any] = json.load(f)
                apis: Dict[str, Any] = data.get("apis", {})
                ac_data: Dict[str, Any] = data.get("ac", {})
                ip: str = str(apis.get("AC_IP", ac_data.get("ip", "")))
                device_id: int = int(apis.get("AC_ID", ac_data.get("device_id", 0)))
                if ip:
                    return ip, device_id
        except Exception as e:
            print(f"⚠️ Error cargando configuración: {e}")

    return "", 0

IP, DEVICE_ID = load_ac_config()

def send_event(event_name: str, payload: Any) -> None:
    """Envía un evento UDP al Brain de Fina de forma segura"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            message: str = json.dumps({
                "type": "event",
                "event": event_name,
                "name": event_name,
                "payload": payload,
                "module": "clima"
            })
            sock.sendto(message.encode(), ("127.0.0.1", 5555))
    except Exception as e:
        print(f"Error enviando evento UDP: {e}")

async def control_aire() -> None:
    """Manejador principal de control de aire acondicionado Midea/Surrey"""
    parser = argparse.ArgumentParser(description="Control de Aire Acondicionado Surrey/Midea")
    parser.add_argument("--power", choices=["on", "off"])
    parser.add_argument("--temp", type=float)
    parser.add_argument("--swing", choices=["on", "off"])
    parser.add_argument("--turbo", choices=["on", "off"])
    parser.add_argument("--mode", choices=["auto", "cool", "dry", "heat", "fan"])
    parser.add_argument("--fan", choices=["auto", "low", "medium", "high", "full"])
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--silent", action="store_true")
    parser.add_argument("--ip", type=str, help="IP del equipo AC")
    parser.add_argument("--lang", type=str, default="es")
    args = parser.parse_args()

    lang: str = str(args.lang)

    def get_i18n(key: str, default: str) -> str:
        """Resuelve traducciones locales sin dependencias externas"""
        translations: Dict[str, Dict[str, str]] = {
            "err_offline": {"es": "Error: El dispositivo parece estar offline.", "en": "Error: Device seems to be offline."},
            "err_no_connect": {"es": "No pude conectar con el aire acondicionado.", "en": "Could not connect to the air conditioner."},
            "status_on": {"es": "encendido", "en": "on"},
            "status_off": {"es": "apagado", "en": "off"},
            "mode_unknown": {"es": "Desconocido", "en": "Unknown"},
            "msg_status": {
                "es": "El aire está {estado} en modo {modo} a {temp}°C. Consumo: {watts}W. Acumulado: {total}kWh. Int: {in_t}°C | Ext: {out_t}°C.",
                "en": "The AC is {estado} in {modo} mode at {temp}°C. Power: {watts}W. Total: {total}kWh. In: {in_t}°C | Out: {out_t}°C."
            },
            "msg_hum": {"es": " Humedad: {h}%", "en": " Humidity: {h}%"},
            "msg_ac_power": {"es": "Aire acondicionado {estado}.", "en": "Air conditioner {estado}."},
            "msg_ac_temp": {"es": "Aire a {t} grados.", "en": "AC set to {t} degrees."},
            "msg_ac_range": {"es": "Temperatura fuera de rango (17-30).", "en": "Temperature out of range (17-30)."},
            "msg_ac_mode": {"es": "Modo {m} activado.", "en": "Mode {m} activated."},
            "msg_ac_fan": {"es": "Ventilador en {f}.", "en": "Fan set to {f}."},
            "msg_ac_swing": {"es": "Swing {s}.", "en": "Swing {s}."},
            "msg_ac_turbo": {"es": "Turbo {s}.", "en": "Turbo {s}."},
            "val_enabled": {"es": "activado", "en": "enabled"},
            "val_disabled": {"es": "desactivado", "en": "disabled"},
        }
        return translations.get(key, {}).get(lang, default)

    target_ip: str = str(args.ip) if args.ip else IP
    if not target_ip:
        print("✗ No se detectó IP del AC. Usá --ip o configurá settings.json")
        return

    try:
        device: Any = AC(ip=target_ip, port=6444, device_id=DEVICE_ID) # type: ignore

        # --- CONSULTA DE ESTADO ---
        if args.status:
            connected: bool = False
            for i in range(3):
                try:
                    await device.refresh() # type: ignore
                    if device.online: # type: ignore
                        connected = True
                        break
                except Exception as e:
                    print(f"Intento {i+1} fallido: {e}")
                await asyncio.sleep(1)

            if not connected:
                print(get_i18n("err_offline", "Error: Offline"))
                if not args.silent:
                    send_event("fina-speak", get_i18n("err_no_connect", "No pude conectar."))
                return

            estado: str = get_i18n("status_on" if device.power_state else "status_off", "encendido") # type: ignore
            mode_names: Dict[int, str] = {1: "Auto", 2: "Cool", 3: "Dry", 4: "Heat", 5: "Fan"}
            modo_actual: str = mode_names.get(int(device.operational_mode), get_i18n("mode_unknown", "Desconocido")) # type: ignore

            # --- OBTENER ENERGÍA (HACK SURREY) ---
            watts: float = 0.0
            total_kwh: float = 0.0
            try:
                # 1. Energía Acumulada (Sub-cmd 0x44)
                found_energy: bool = False
                for _ in range(3):
                    resp_energy = await device._send_commands_get_responses([EnergyHackCommand(0x44)]) # type: ignore
                    if resp_energy:
                        for r in resp_energy:
                            if hasattr(r, 'payload') and len(r.payload) > 7 and r.payload[3] == 0x44:
                                # d[4]=1000s, d[5]=100s/10s, d[6]=1s, d[7]=0.1s/0.01s
                                val_high = decode_bcd(r.payload[4]) * 100 + decode_bcd(r.payload[5])
                                val_low = decode_bcd(r.payload[6]) + (decode_bcd(r.payload[7]) / 100.0)
                                total_kwh = val_high + val_low
                                found_energy = True
                                break
                    if found_energy:
                        break
                    await asyncio.sleep(0.4)

                # 2. Potencia Instantánea (Sub-cmd 0x43) — solo si está encendido
                if device.power_state: # type: ignore
                    for _ in range(3):
                        resp_power = await device._send_commands_get_responses([EnergyHackCommand(0x43)]) # type: ignore
                        if resp_power:
                            found_43: bool = False
                            for r in resp_power:
                                if hasattr(r, 'payload') and len(r.payload) > 16 and r.payload[3] == 0x43:
                                    watts = float(r.payload[16] * 10)
                                    found_43 = True
                                    break
                            if found_43:
                                break
                        await asyncio.sleep(0.3)
            except Exception as energy_err:
                if not args.silent:
                    print(f"Error obteniendo energía: {energy_err}")
            # -----------------------------------

            msg: str = get_i18n("msg_status", "").format(
                estado=estado,
                modo=modo_actual,
                temp=int(device.target_temperature), # type: ignore
                watts=int(watts),
                total=round(total_kwh, 2), # type: ignore
                in_t=int(device.indoor_temperature), # type: ignore
                out_t=int(device.outdoor_temperature or 0) # type: ignore
            )
            if device.indoor_humidity: # type: ignore
                msg += get_i18n("msg_hum", " Humedad: {h}%").format(h=device.indoor_humidity) # type: ignore

            send_event("ac-status-update", {
                "power": bool(device.power_state), # type: ignore
                "temp": float(device.target_temperature), # type: ignore
                "mode": modo_actual.upper(),
                "indoor": float(device.indoor_temperature), # type: ignore
                "outdoor": float(device.outdoor_temperature or 0), # type: ignore
                "watts": watts,
                "total_kwh": round(total_kwh, 2) # type: ignore
            })

            print(msg)
            if not args.silent:
                send_event("fina-speak", msg)
            return

        # --- EJECUCIÓN DE ACCIONES ---
        needs_apply: bool = False
        action_msg: str = ""

        if args.power:
            device.power_state = (args.power == "on") # type: ignore
            needs_apply = True
            estado_p: str = get_i18n("status_on" if device.power_state else "status_off", "ok") # type: ignore
            action_msg = get_i18n("msg_ac_power", "").format(estado=estado_p)

        if args.temp:
            if 17 <= args.temp <= 30:
                device.target_temperature = args.temp # type: ignore
                device.power_state = True # type: ignore
                needs_apply = True
                if not action_msg:
                    action_msg = get_i18n("msg_ac_temp", "Aire a {t} grados.").format(t=args.temp)
            else:
                print(get_i18n("msg_ac_range", "Temperatura fuera de rango (17-30)."))

        if args.mode:
            mode_map: Dict[str, int] = {"auto": 1, "cool": 2, "dry": 3, "heat": 4, "fan": 5}
            device.operational_mode = mode_map.get(args.mode, 2) # type: ignore
            device.power_state = True # type: ignore
            needs_apply = True
            if not action_msg:
                action_msg = get_i18n("msg_ac_mode", "Modo {m} activado.").format(m=args.mode)

        if args.fan:
            speeds: Dict[str, int] = {"auto": 102, "low": 40, "medium": 60, "high": 80, "full": 100}
            device.fan_speed = speeds.get(args.fan, 102) # type: ignore
            needs_apply = True
            if not action_msg:
                action_msg = get_i18n("msg_ac_fan", "Ventilador en {f}.").format(f=args.fan)

        if args.swing:
            device.swing_mode = 0x0C if args.swing == "on" else 0x00 # type: ignore
            needs_apply = True
            if not action_msg:
                val_s: str = get_i18n("val_enabled" if args.swing == "on" else "val_disabled", "ok")
                action_msg = get_i18n("msg_ac_swing", "Swing {s}.").format(s=val_s)

        if args.turbo:
            device.turbo = (args.turbo == "on") # type: ignore
            needs_apply = True
            if not action_msg:
                val_t: str = get_i18n("val_enabled" if args.turbo == "on" else "val_disabled", "ok")
                action_msg = get_i18n("msg_ac_turbo", "Turbo {s}.").format(s=val_t)

        if needs_apply:
            device.beep = True # type: ignore
            await device.apply() # type: ignore
            if action_msg:
                print(action_msg)
                if not args.silent:
                    send_event("fina-speak", action_msg)

    except Exception as e:
        print(f"Error controlando el aire: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(control_aire())
    except KeyboardInterrupt:
        pass
    except Exception as fatal:
        print(f"✗ Fatal: {fatal}")
        sys.exit(1)
