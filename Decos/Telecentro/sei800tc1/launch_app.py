#!/usr/bin/env python3
"""
launch_app.py - Lanza una aplicación instalada en un Decodificador Android TV vía ADB.
"""
import subprocess
import argparse
import sys
import os
import logging
from typing import List, Any

# Configuración de logging básica
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger("launch_app")

def launch_application(ip: str, package: str) -> None:
    """Intenta lanzar una app usando monkey y am start como fallback"""
    logger.info(f"🚀 Lanzando '{package}' en dispositivo ({ip})...")
    
    try:
        # 1. Asegurar conexión preactiva
        subprocess.run(["adb", "connect", f"{ip}:5555"], capture_output=True, timeout=3) # type: ignore
        
        # 2. Comando Monkey (Lanzador universal de actividades principales en Android)
        adb_monkey: List[str] = ["adb", "-s", f"{ip}:5555", "shell", "monkey", "-p", package, "1"]
        res = subprocess.run(adb_monkey, capture_output=True, text=True, timeout=5) # type: ignore
        
        if res.returncode == 0:
            logger.info(f"✅ ¡Aplicación '{package}' lanzada con éxito!")
        else:
            logger.warning(f"⚠️ El comando ADB (Monkey) no pudo iniciar '{package}'. Probando fallback...")
            # Fallback con 'am start' intentando la actividad principal común
            common_activities = [".MainActivity", ".TvActivity", ".Main"]
            success = False
            for act in common_activities:
                fallback_cmd: List[str] = ["adb", "-s", f"{ip}:5555", "shell", "am", "start", "-n", f"{package}/{act}"]
                res_fallback = subprocess.run(fallback_cmd, capture_output=True, timeout=3) # type: ignore
                if res_fallback.returncode == 0:
                    logger.info(f"✅ ¡Aplicación lanzada con '{act}'!")
                    success = True
                    break
            
            if not success:
               logger.error("❌ No fue posible lanzar la aplicación por ningún método.")
               sys.exit(1)
            
    except Exception as e:
         logger.error(f"❌ Error al lanzar la app: {e}")
         sys.exit(1)

def main() -> None:
    """Función de entrada CLI"""
    parser = argparse.ArgumentParser(description="Lanzar aplicación en Deco Android TV vía ADB")
    parser.add_argument("--ip", required=True, help="IP del Deco")
    parser.add_argument("--package", required=True, help="ID del paquete (ej: com.netflix.ninja)")
    args = parser.parse_args()
    
    launch_application(args.ip, args.package)

if __name__ == "__main__":
    main()
