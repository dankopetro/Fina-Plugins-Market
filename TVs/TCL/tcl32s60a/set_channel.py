
import subprocess
import time
import argparse
import sys
import os
import json

# Adjust project root if needed
# ./plugins/tv/tcl_32s60a/set_channel.py
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))

# Mapping of digits to ADB Key Events
KEY_MAP = {
    "0": "KEYCODE_0",
    "1": "KEYCODE_1",
    "2": "KEYCODE_2",
    "3": "KEYCODE_3",
    "4": "KEYCODE_4",
    "5": "KEYCODE_5",
    "6": "KEYCODE_6",
    "7": "KEYCODE_7",
    "8": "KEYCODE_8",
    "9": "KEYCODE_9",
    "enter": "KEYCODE_ENTER",
    "ok": "KEYCODE_DPAD_CENTER",
    "channel_up": "KEYCODE_CHANNEL_UP",
    "channel_down": "KEYCODE_CHANNEL_DOWN",
    ".": "KEYCODE_NUMPAD_DOT",
    "-": "KEYCODE_MINUS"
}

def load_channels():
    """Carga mapa de canales (nombre -> numero) de settings o channels.json"""
    channels = {}
    
    # 1. Rutas locales de Fina-Ergen
    paths = [
        os.path.join(PROJECT_ROOT, "config", "channels.json"),
        os.path.join(PROJECT_ROOT, "config", "channels_telecentro.json")
    ]
    
    for p in paths:
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        for ch in data:
                            if "name" in ch and "number" in ch:
                                 key = ch["name"].lower().replace(" ", "").strip()
                                 channels[key] = ch["number"]
                    elif isinstance(data, dict):
                        for name, number in data.items():
                            key = name.lower().replace(" ", "").strip()
                            channels[key] = str(number)
                    
                    if channels: 
                        print(f"📖 Cargados {len(channels)} canales desde {p}")
                        return channels
            except Exception as e: 
                print(f"⚠️ Error cargando {p}: {e}")
                pass
            
    return channels

def get_channel_number(query, channel_map):
    """Busca el número de canal para el nombre dado"""
    # 1. Si es dígito directo, devolverlo
    # Manejar formatos como "13.1" o "13-1" o "13"
    import re
    if re.match(r'^[\d\.\-]+$', query):
        return query
        
    # 2. Buscar en mapa (fuzzy logic simple: substring)
    q = query.lower().replace(" ", "")
    for name, number in channel_map.items():
        if q in name or name in q:
             return number
             
    return None

def send_adb_key(ip, key_code):
    cmd = ["adb", "-s", f"{ip}:5555", "shell", "input", "keyevent", key_code]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def change_channel(ip, channel_number):
    print(f"🚀 Sintonizando {channel_number} en {ip} (Modo Ráfaga)...")
    
    # Mapeo de teclas para TCL
    key_map_tcl = {
        '0': '7', '1': '8', '2': '9', '3': '10', '4': '11',
        '5': '12', '6': '13', '7': '14', '8': '15', '9': '16',
        '.': '158', '-': '69'
    }
    
    # Construir lista de keycodes
    keycodes = [key_map_tcl.get(d) for d in str(channel_number) if key_map_tcl.get(d)]
    
    if keycodes:
        # Enviar ráfaga (todos los números de un solo golpe)
        cmd = ["adb", "-s", f"{ip}:5555", "shell", "input", "keyevent"] + keycodes
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # Pequeña pausa antes del ENTER para asegurar que la TV procesó la ráfaga
        time.sleep(0.1)
        send_adb_key(ip, "66") # ENTER
        print("✅ Canal enviado con éxito.")
    else:
        print(f"⚠️ No se pudo procesar el número: {channel_number}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ip", required=True, help="IP de la TV")
    parser.add_argument("--channel", required=True, help="Nombre o número del canal")
    args = parser.parse_args()
    
    channel_map = load_channels()
    target_number = get_channel_number(args.channel, channel_map)
    
    if target_number:
        change_channel(args.ip, target_number)
    else:
        print(f"❌ No encontré el canal '{args.channel}' en mi lista.")
        sys.exit(1)

if __name__ == "__main__":
    main()
