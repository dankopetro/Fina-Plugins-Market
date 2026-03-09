#!/usr/bin/env python3
import asyncio
import sys
import os
import logging
from typing import Dict, Any, Optional
from msmart.device import AirConditioner as AC # type: ignore

# Configuración de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("ACBlindCool")

# Agregar el directorio actual al path para importar clima_utils
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
try:
    from clima_utils import get_ac_config # type: ignore
except ImportError:
    def get_ac_config() -> Dict[str, Any]:
        """Fallback config loader"""
        return {"ip": "", "device_id": 0}

async def blind_cool() -> None:
    """Envía un comando COOL directo sin refrescar el estado (Modo Ciego)"""
    ac_cfg: Dict[str, Any] = get_ac_config()
    target_ip: str = str(ac_cfg.get("ip", ""))
    device_id: int = int(ac_cfg.get("device_id", 0))

    if not target_ip:
        logger.error("✗ IP no configurada para el modo ciego del Aire Acondicionado.")
        return

    logger.info(f"📡 Enviando comando ciego (baja latencia) a {target_ip}...")
    
    try:
        device = AC(ip=target_ip, port=6444, device_id=device_id) # type: ignore
        # NO REALIZAMOS REFRESH para ganar velocidad de respuesta (Modo Ciego)
        device.power_state = True # type: ignore
        device.operational_mode = 2 # COOL # type: ignore
        device.target_temperature = 22.0 # type: ignore
        device.fan_speed = 60 # type: ignore
        device.eco = False # type: ignore
        device.turbo = False # type: ignore
        device.beep = True # type: ignore
        
        logger.info("Aplicando parámetros de refrigeración directa...")
        await device.apply() # type: ignore
        print("✅ Comando de refrigeración ciega enviado.")
        
    except Exception as e:
        logger.error(f"✗ Error en blind cool: {e}")

def main() -> None:
    """Punto de entrada principal"""
    try:
        asyncio.run(blind_cool())
    except KeyboardInterrupt:
        pass
    except Exception as fatal:
        logger.critical(f"✗ Fatal: {fatal}")
        sys.exit(1)

if __name__ == "__main__":
    main()
