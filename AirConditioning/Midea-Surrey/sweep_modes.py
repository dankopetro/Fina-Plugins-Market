#!/usr/bin/env python3
import asyncio
import os
import sys
import logging
from typing import Dict, Any, Optional
from msmart.device import AirConditioner as AC # type: ignore

# Configuración de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("ACSweep")

# Agregar el directorio actual al path para importar clima_utils
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
try:
    from clima_utils import get_ac_config # type: ignore
except ImportError:
    def get_ac_config() -> Dict[str, Any]:
        """Fallback config loader"""
        return {"ip": "", "device_id": 0}

async def sweep_modes() -> None:
    """Realiza un barrido de todos los modos del AC para validar soporte de hardware"""
    ac_cfg: Dict[str, Any] = get_ac_config()
    target_ip: str = str(ac_cfg.get("ip", ""))
    device_id: int = int(ac_cfg.get("device_id", 0))

    if not target_ip:
        logger.error("✗ IP no configurada para el barrido de modos del Aire Acondicionado.")
        return

    logger.info(f"📡 Iniciando barrido de modos operativos en {target_ip}...")
    
    try:
        device = AC(ip=target_ip, port=6444, device_id=device_id) # type: ignore
        await device.refresh() # type: ignore
        
        mode_names: Dict[int, str] = {1: "Auto", 2: "Cool", 3: "Dry", 4: "Heat", 5: "Fan"}
        
        for m in range(1, 6):
            logger.info(f"--- Probando Modo {m} ({mode_names[m]}) ---")
            device.power_state = True # type: ignore
            device.operational_mode = m # type_ignore
            await device.apply() # type: ignore
            
            await asyncio.sleep(2)
            await device.refresh() # type: ignore
            
            real_mode: int = int(device.operational_mode) # type: ignore
            logger.info(f"Estado real tras seteo {m}: {real_mode} ({mode_names.get(real_mode, '???')})")
            
        print("✅ Barrido de modos completado.")
            
    except Exception as e:
        logger.error(f"✗ Error durante el barrido de diagnóstico: {e}")

def main() -> None:
    """Punto de entrada principal"""
    try:
        asyncio.run(sweep_modes())
    except KeyboardInterrupt:
        pass
    except Exception as fatal:
        logger.critical(f"✗ Fatal: {fatal}")
        sys.exit(1)

if __name__ == "__main__":
    main()
