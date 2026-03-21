#!/usr/bin/env python3
import asyncio
import sys
import os
import argparse

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
try:
    from deco_remote_helper import send_command # type: ignore
except ImportError:
    from .deco_remote_helper import send_command # type: ignore

# Carga de pychromecast con guard
try:
    import pychromecast # type: ignore
    HAS_CHROMECAST = True
except ImportError:
    HAS_CHROMECAST = False

async def wake_via_cast(ip: str) -> None:
    """
    Fuerza el despertar del dispositivo y la TV vía HDMI-CEC activando
    una aplicación de Cast (YouTube) de forma efímera.
    """
    if not HAS_CHROMECAST:
        return

    try:
        cast = pychromecast.Chromecast(ip) # type: ignore
        cast.wait(timeout=3) # type: ignore
        cast.start_app("233637DE")  # App ID de YouTube
        await asyncio.sleep(2)
        cast.quit_app() # type: ignore
    except Exception as e:
        pass

async def turn_on(ip: str) -> None:
    success = await send_command(ip, "power_on")
    if success:
        # Disparar wake fallback para asegurar HDMI-CEC y salida de deep sleep
        await wake_via_cast(ip)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Encender Deco Telecentro")
    parser.add_argument("--ip", required=True, help="IP del Decodificador")
    args = parser.parse_args()
    try:
        asyncio.run(turn_on(args.ip))
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"✗ Error: {e}")
        sys.exit(1)
