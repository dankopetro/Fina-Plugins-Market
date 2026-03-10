#!/usr/bin/env python3
"""
tv_power.py - Alterna el estado de energía de un Decodificador Android TV (SEI800TC1).
Utiliza 'androidtvremote2' vía remote_helper y opcionalmente PyChromecast para despertar vía HDMI-CEC.
"""
import asyncio
import sys
import os
import argparse
import logging
from typing import Optional, Any

# Configuración de logging básica
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger("tv_power")

# Carga de pychromecast con guard
try:
    import pychromecast # type: ignore
    HAS_CHROMECAST = True
except ImportError:
    HAS_CHROMECAST = False

# Agregar el directorio actual al path para importar remote_helper
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
try:
    from remote_helper import send_command, check_if_on # type: ignore
except ImportError:
    # Fallback si falla el import relativo
    from .remote_helper import send_command, check_if_on # type: ignore

async def wake_via_cast(ip: str) -> None:
    """
    Fuerza el despertar del dispositivo y la TV vía HDMI-CEC activando
    una aplicación de Cast (YouTube) de forma efímera.
    """
    if not HAS_CHROMECAST:
        logger.debug("Chromecast no disponible. Saltando wake_via_cast.")
        return

    logger.info(f"📡 Intentando despertar dispositivo vía Cast en {ip}...")
    try:
        # pychromecast es bloqueante, en una versión ideal usaríamos algo asíncrono
        # pero para compatibilidad mantenemos la lógica pero con mejor manejo
        cast = pychromecast.Chromecast(ip) # type: ignore
        cast.wait(timeout=3) # type: ignore
        cast.start_app("233637DE")  # App ID de YouTube
        await asyncio.sleep(2)
        cast.quit_app() # type: ignore
    except Exception as e:
        logger.warning(f"⚠️ No se pudo despertar vía Cast: {e}")

async def toggle_power(ip: str) -> None:
    """Detecta el estado actual y lo invierte"""
    try:
        is_on: bool = await check_if_on(ip)
        logger.info(f"📟 Estado actual del dispositivo ({ip}): {'ENCENDIDO' if is_on else 'APAGADO'}")
        
        if is_on:
            logger.info("⚡ Enviando comando de apagado...")
            success = await send_command(ip, "power_off")
            if success:
                logger.info("✅ Comando de apagado enviado.")
        else:
            logger.info("⚡ Enviando comando de encendido...")
            success = await send_command(ip, "power_on")
            if success:
                logger.info("✅ Comando de encendido enviado.")
                # Disparar wake fallback para asegurar HDMI-CEC
                await wake_via_cast(ip)
                
    except Exception as e:
        logger.error(f"❌ Error en toggle_power: {e}")

def main() -> None:
    parser = argparse.ArgumentParser(description="Alternar encendido/apagado del Deco Android TV")
    parser.add_argument("--ip", required=True, help="IP del dispositivo")
    parser.add_argument("--mac", help="Dirección MAC (opcional)")
    args = parser.parse_args()
    
    try:
        asyncio.run(toggle_power(args.ip))
    except KeyboardInterrupt:
        logger.info("\n⏹ Operación cancelada por el usuario.")
    except Exception as e:
        logger.error(f"✗ Fatal: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
