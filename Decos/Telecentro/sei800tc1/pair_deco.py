#!/usr/bin/env python3
"""
pair_deco.py - Proceso guiado de emparejamiento para Decodificadores Android TV (SEI800TC1).
Establece una conexión segura con el dispositivo y genera certificados de confianza (cert.pem/key.pem).
"""
import asyncio
import os
import sys
import argparse
import logging
import socket
import concurrent.futures
from typing import Optional, List, Any

# Configuración de logging profesional
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger("pair_deco")

# Carga de la librería principal con guard
try:
    from androidtvremote2 import AndroidTVRemote # type: ignore
except ImportError:
    logger.error("❌ Librería 'androidtvremote2' no instalada.")
    sys.exit(1)

# Rutas de certificados en la carpeta del script (donde los busca deco_remote_helper)
BASE_DIR: str = os.path.dirname(os.path.abspath(__file__))
CERT_PATH: str = os.path.join(BASE_DIR, "cert.pem")
KEY_PATH: str = os.path.join(BASE_DIR, "key.pem")

def auto_discover_deco() -> Optional[str]:
    """Escaneo rápido multihilo para encontrar dispositivos con puerto 6466 abierto"""
    logger.info("\n🔍 Buscando Decodificador en la red automáticamente...")
    
    base_ip: str = "192.168.0."
    try:
        # Intenta detectar la red local real
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            base_ip = ".".join(s.getsockname()[0].split('.')[:-1]) + "."
    except Exception:
        pass

    def check_port(ip: str) -> Optional[str]:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.3)
                if s.connect_ex((ip, 6466)) == 0:
                    return ip
        except Exception:
            pass
        return None

    ips: List[str] = [f"{base_ip}{i}" for i in range(1, 255)]
    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        found: List[str] = [r for r in executor.map(check_port, ips) if r]

    if found:
        logger.info(f"✅ ¡Encontré un dispositivo en: {found[0]}!")
        return found[0]
    
    logger.warning("❌ No se encontró ningún Deco automáticamente.")
    return None

async def pair_process(ip: Optional[str] = None) -> None:
    """Orquesta el flujo de emparejamiento paso a paso"""
    target_ip: Optional[str] = ip
    if not target_ip:
        target_ip = auto_discover_deco()
        if not target_ip:
            logger.info("💡 Por favor, asegúrate de que el Deco esté encendido y en la misma red Wi-Fi.")
            return

    logger.info(f"\n{'─'*50}\n🛰️  INICIANDO ASOCIACIÓN CON DECO '{target_ip}'\n{'─'*50}")
    logger.info("📺 Mirá la pantalla del televisor/deco. Debería aparecer un PIN de 6 dígitos.")

    remote = AndroidTVRemote(
        client_name="Fina Ergen Pairing",
        certfile=CERT_PATH,
        keyfile=KEY_PATH,
        host=target_ip
    )

    try:
        # Generación de llaves si no existen
        if await remote.async_generate_cert_if_missing(): # type: ignore
            logger.info("✨ Se han generado nuevas credenciales de seguridad locales.")

        # Iniciar handshake
        await remote.async_start_pairing() # type: ignore
        
        # Entrada de PIN manual (único paso humano requerido)
        print("\n" + "🔑" + " "*2, end="")
        pin: str = input("Ingresa el código que aparece en la TV: ").strip()
        
        # Concluir proceso
        await remote.async_finish_pairing(pin) # type: ignore
        
        logger.info("\n✅ ¡ASOCIACIÓN EXITOSA! Fina ya tiene control total del Deco.")
        logger.info(f"📄 Credenciales guardadas en: {BASE_DIR}")
                
    except Exception as e:
        logger.error(f"\n❌ Error durante el emparejamiento: {e}")
        if "Connection refused" in str(e):
            logger.info("💡 Tip: Verifica que no haya otra sesión de emparejamiento abierta.")

def main() -> None:
    parser = argparse.ArgumentParser(description="Emparejar Fina con un Decodificador Android TV")
    parser.add_argument("--ip", help="IP del Deco (se intentará auto-detectar si se omite)")
    parser.add_argument("--force", action="store_true", help="Sobreescribir certificados existentes")
    args = parser.parse_args()

    # Verificar existencia de llaves previa
    if os.path.exists(CERT_PATH) and not args.force:
        logger.info(f"⚠️ Ya existe una asociación activa en: {CERT_PATH}")
        resp: str = input("¿Deseas re-asociar y sobreescribir las llaves? (S/N): ").lower()
        if resp != 's':
            logger.info("Operación cancelada.")
            return

    try:
        asyncio.run(pair_process(args.ip))
    except KeyboardInterrupt:
        logger.info("\n⏹ Proceso cancelado por el usuario.")
    except Exception as e:
        logger.error(f"\n✗ Fatal: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
