#!/usr/bin/env python3
import asyncio
import sys
import argparse
import os
import json
from remote_helper import send_command

# Ajustar PROJECT_ROOT
# ./plugins/tv/sei800tc1/set_channel.py
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))

def load_channels():
    """Carga el mapeo de canales del archivo JSON (admite diccionario o lista)"""
    channels = {}
    # Priorizamos el de Telecentro para este modelo
    paths = [
        os.path.join(PROJECT_ROOT, "config", "channels_telecentro.json"),
        os.path.join(PROJECT_ROOT, "config", "channels.json")
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

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ip", required=True)
    parser.add_argument("--channel", required=True)
    args = parser.parse_args()

    channel_to_send = args.channel
    
    # 1. Intentar mapear nombre a número
    if not args.channel.replace(".", "").replace("-", "").isdigit():
        channels_map = load_channels()
        key = args.channel.lower().replace(" ", "").strip()
        if key in channels_map:
            channel_to_send = channels_map[key]
            print(f"🎯 Mapeado '{args.channel}' -> {channel_to_send}")
        else:
            print(f"❌ No encontré el canal '{args.channel}' en mi lista.")
            # Intentamos enviarlo igual por si acaso es un número que no estaba en la lista
    
    print(f"📺 Sintonizando canal {channel_to_send} en {args.ip}...")
    await send_command(args.ip, "channel", channel_to_send)

if __name__ == "__main__":
    asyncio.run(main())
