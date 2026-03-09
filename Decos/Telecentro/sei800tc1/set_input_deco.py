#!/usr/bin/env python3
"""
set_input_deco.py - Cambia a la entrada del Decodificador en la TV.
En un dispositivo 'Deco', esta acción suele interpretarse como volver al Home 
del sistema para que la TV cambie su entrada vía HDMI-CEC.
"""
import asyncio
import sys
import os
import argparse
import logging
from typing import Optional, Any

# Configuración de logging básica
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger("set_input_deco")

# Agregar el directorio actual al path para importar remote_helper
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
try:
    from remote_helper import send_command # type: ignore
except ImportError:
    # Fallback si falla el import relativo
    from .remote_helper import send_command # type: ignore

async def set_input(ip: str) -> None:
    """Intenta despertar y volver al home para activar CEC"""
    logger.info(f"⚡ Activando entrada del Deco en {ip}...")
    try:
        # Enviamos un comando neutro (HOME) que suele disparar el CEC de la TV 
        # para que cambie al HDMI del Deco automáticamente.
        success = await send_command(ip, "key", "KEYCODE_HOME")
        if success:
            logger.info("✅ Comando HOME enviado (Activa HDMI-CEC de la TV).")
        else:
            logger.info("⚠️ No fue posible enviar el comando al Deco.")
            
    except Exception as e:
        logger.error(f"❌ Error en set_input_deco: {e}")

def main() -> None:
    parser = argparse.ArgumentParser(description="Cambiar a la entrada HDMI del Deco (vía HDMI-CEC)")
    parser.add_argument("--ip", required=True, help="IP del Deco")
    parser.add_argument("--input", help="Nombre de la entrada (no usado)")
    args = parser.parse_args()
    
    try:
        asyncio.run(set_input(args.ip))
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.error(f"✗ Fatal: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
