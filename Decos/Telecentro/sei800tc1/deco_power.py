
import asyncio
import sys
import os
import argparse
import pychromecast

# Agregar el directorio actual al path para importar remote_helper
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from remote_helper import send_command, check_if_on

async def wake_via_cast(ip):
    print("📡 Forzando despertar via Cast (YouTube trigger)...")
    try:
        # Esto suele forzar a la TV a cambiar al HDMI del Deco
        cast = pychromecast.Chromecast(ip)
        cast.wait(timeout=5)
        cast.start_app("233637DE") # YouTube 
        await asyncio.sleep(3)
        cast.quit_app()
    except Exception as e:
        print(f"⚠️ Error en Cast: {e}")

async def toggle_power(ip):
    is_on = await check_if_on(ip)
    print(f"📟 Estado actual del Deco: {'ON' if is_on else 'OFF'}")
    
    if is_on:
        print("⚡ Apagando Deco (Smart)...")
        await send_command(ip, "power_off")
    else:
        print("⚡ Encendiendo Deco (Smart)...")
        await send_command(ip, "power_on")
        # El usuario notó que esto ayuda a que la TV cambie de entrada sola
        await wake_via_cast(ip)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--ip", required=True)
    parser.add_argument("--mac", help="MAC (no usada por ahora en Deco)")
    args = parser.parse_args()
    asyncio.run(toggle_power(args.ip))
