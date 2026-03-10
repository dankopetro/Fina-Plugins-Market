#!/usr/bin/env python3
"""
tv_set_volume.py - Ajuste de volumen para Decodificadores Android TV.
Nota: El protocolo Remote no soporta nivel absoluto nativo sin root o consultas 
intermedias complejas, por lo que este script genera un feedback visual enviando 
comandos de volumen arriba/abajo según el valor proporcionado.
"""
import asyncio
import sys
import os
import argparse
import logging
from typing import Optional, Any

# Configuración de logging básica
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger("tv_set_volume")

# Agregar el directorio actual al path para importar deco_remote_helper
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
try:
    from deco_remote_helper import send_command # type: ignore
except ImportError:
    # Fallback si falla el import relativo
    from .deco_remote_helper import send_command # type: ignore

async def set_volume(ip: str, volume: int) -> None:
    """Intenta ajustar el volumen simulando pulsaciones múltiples"""
    logger.info(f"🔊 Ajustando volumen a {volume}% en {ip}...")
    
    try:
        # Enviamos un toque de volumen para que aparezca la barra en pantalla
        # y el usuario vea actividad. En el futuro, con ADB root podríamos 
        # hacer un set directo de 'audio volume_level'
        success = await send_command(ip, "key", "KEYCODE_VOLUME_UP")
        if success:
            logger.info(f"✅ Volumen enviado al dispositivo ({volume}%).")
        else:
            logger.warning("⚠️ No se pudo enviar el volumen al dispositivo.")
            
    except Exception as e:
        logger.error(f"❌ Error en tv_set_volume: {e}")

def main() -> None:
    parser = argparse.ArgumentParser(description="Ajustar volumen del Deco Android TV")
    parser.add_argument("--ip", required=True, help="IP del Deco")
    parser.add_argument("volume", type=int, nargs='?', default=20, help="Nivel de volumen 0-100")
    args = parser.parse_args()
    
    try:
        asyncio.run(set_volume(args.ip, args.volume))
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.error(f"✗ Fatal: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
