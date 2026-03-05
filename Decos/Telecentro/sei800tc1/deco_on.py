
import asyncio
import argparse
import pychromecast
from remote_helper import send_command

import socket

def wake_on_lan(macaddress, ip_hint=None):
    """Envia un paquete Magic Packet para despertar el dispositivo"""
    if not macaddress: return False
    
    # Normalizar MAC
    mac = macaddress.replace(':', '').replace('-', '')
    if len(mac) != 12: return False

    # Crear el magic packet
    data = b'f' * 12 + (bytes.fromhex(mac) * 16)
    
    # Enviar por broadcast y hint
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    
    try:
        sock.sendto(data, ('255.255.255.255', 9))
        if ip_hint: sock.sendto(data, (ip_hint, 9))
        return True
    except: return False
    finally: sock.close()

async def wake_via_cast(ip):
    print(f"Despertando via Cast en {ip}...")
    try:
        cast = pychromecast.Chromecast(ip)
        cast.wait()
        cast.start_app("233637DE") # YouTube as trigger
        await asyncio.sleep(5)
        cast.quit_app()
    except:
        pass

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ip", required=True)
    parser.add_argument("--mac", help="MAC para WoL")
    args = parser.parse_args()

    print(f"--- ENCENDIENDO DECO ({args.ip}) ---")
    
    # 0. WoL (Si hay MAC)
    if args.mac:
        print(f"📡 Enviando WoL a {args.mac}...")
        wake_on_lan(args.mac, args.ip)
        await asyncio.sleep(1)

    # 1. Primero intentamos Power Key (vía IP Bluetooth/Network)
    print(f"🔌 Enviando Power ON vía red...")
    await send_command(args.ip, "power_on")
    
    # 2. Adicionalmente disparamos Cast
    await wake_via_cast(args.ip)

if __name__ == "__main__":
    asyncio.run(main())
