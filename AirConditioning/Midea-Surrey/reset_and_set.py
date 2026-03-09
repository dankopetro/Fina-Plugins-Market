#!/usr/bin/env python3
import asyncio
import sys
import os
import logging
from typing import Dict, Any, Optional
from msmart.device import AirConditioner as AC # type: ignore

# Configuración de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("ACReset")

# Agregar el directorio actual al path para importar clima_utils
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
try:
    from clima_utils import get_ac_config # type: ignore
except ImportError:
    def get_ac_config() -> Dict[str, Any]:
        """Fallback config loader"""
        return {"ip": "", "device_id": 0}

async def reset_and_set() -> None:
    """Reinicia el AC (Apagar) y lo setea en modo COOL como reset básico"""
    ac_cfg: Dict[str, Any] = get_ac_config()
    target_ip: str = str(ac_cfg.get("ip", ""))
    device_id: int = int(ac_cfg.get("device_id", 0))

    if not target_ip:
        logger.error("✗ IP no configurada para el reinicio del Aire Acondicionado.")
        return

    logger.info(f"📡 Iniciando ciclo de reinicio y configuración en {target_ip}...")
    
    try:
        device = AC(ip=target_ip, port=6444, device_id=device_id) # type: ignore
        await device.refresh() # type: ignore
        logger.info(f"Modo Inicial: {device.operational_mode}") # type: ignore
        
        logger.info("Encendiendo/Apagando para resetear estado...")
        device.power_state = False # type: ignore
        await device.apply() # type: ignore
        await asyncio.sleep(2)
        
        logger.info("Estableciendo modo COOL (Refrigeración)...")
        device.power_state = True # type: ignore
        device.operational_mode = 2 # COOL # type: ignore
        device.target_temperature = 24.0 # Temperatura de confort por defecto
        await device.apply() # type: ignore
        
        await asyncio.sleep(2)
        await device.refresh() # type: ignore
        logger.info(f"Modo Final Establecido: {device.operational_mode}") # type: ignore
        print("✅ Aire acondicionado reiniciado con éxito.")
        
    except Exception as e:
        logger.error(f"✗ Error durante el ciclo de reinicio: {e}")

def main() -> None:
    """Punto de entrada principal"""
    try:
        asyncio.run(reset_and_set())
    except KeyboardInterrupt:
        pass
    except Exception as fatal:
        logger.critical(f"✗ Fatal: {fatal}")
        sys.exit(1)

if __name__ == "__main__":
    main()
