#!/usr/bin/env python3
"""
tv_input.py - Cambia a la entrada HDMI del Decodificador en la TV.
En un dispositivo 'Deco' Android TV, esta acción suele interpretarse como volver al 
Launcher Principal (Home) para forzar a la TV a sintonizar su HDMI vía CEC.
"""
import asyncio
import sys
import os
import argparse
import logging
from typing import Optional, Any

# Configuración de logging básica
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger("tv_input")

# Agregar el directorio actual al path para importar remote_helper
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
try:
    from remote_helper import send_command # type: ignore
except ImportError:
    # Fallback si falla el import relativo
    from .remote_helper import send_command # type: ignore

async def set_tv_input(ip: str) -> None:
    """Envía un comando HOME para despertar el CEC del dispositivo"""
    logger.info(f"⚡ Intentando activar entrada del Deco ({ip})...")
    try:
        # Enviamos KEYCODE_HOME para que el Deco tome el control del HDMI de la TV
        success = await send_command(ip, "key", "KEYCODE_HOME")
        if success:
            logger.info("✅ Comando 'HOME' enviado con éxito. HDMI-CEC debería activarse.")
        else:
            logger.warning("⚠️ No se pudo enviar el comando al dispositivo.")
            
    except Exception as e:
        logger.error(f"❌ Error en tv_input: {e}")

def main() -> None:
    parser = argparse.ArgumentParser(description="Cambiar entrada HDMI al Decodificador (vía CEC)")
    parser.add_argument("--ip", required=True, help="IP del dispositivo")
    parser.add_argument("--input", help="Nombre de la entrada (opcional)")
    args = parser.parse_args()
    
    try:
        asyncio.run(set_tv_input(args.ip))
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.error(f"✗ Fatal: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
