import asyncio
import sys
import os
import json
from typing import Any, List, Optional, Dict

# Se asume que androidtvremote2 está instalado
try:
    from androidtvremote2 import AndroidTVRemote # type: ignore
except ImportError:
    AndroidTVRemote = None # type: ignore

def get_config_dir() -> str:
    xdg_config = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config:
        return os.path.join(xdg_config, "Fina")
    return os.path.expanduser("~/.config/Fina")

def load_deco_ip() -> str:
    """Intenta cargar la IP del Deco desde settings.json"""
    paths: List[str] = [
        os.path.join(get_config_dir(), "settings.json")
    ]
    
    # Intentar detectar el root del proyecto para el fallback
    def find_root(curr_dir: str) -> Optional[str]:
        curr = str(curr_dir)
        while curr != str(os.path.dirname(curr)):
            if os.path.exists(str(os.path.join(curr, "package.json"))): # type: ignore
                return str(curr)
            curr = str(os.path.dirname(curr)) # type: ignore
        return None

    root_dir = find_root(os.path.dirname(os.path.abspath(__file__)))
    if root_dir:
        paths.append(os.path.join(root_dir, "config", "settings.json"))
    
    # Fallback legacy
    paths.append(os.path.join(os.path.dirname(__file__), "../../../../config/settings.json"))

    for p in paths:
        if os.path.exists(p):
            try:
                with open(p, "r") as f:
                    data: Dict[str, Any] = json.load(f)
                    # 1. Buscar en apis
                    ip_api = data.get("apis", {}).get("DECO_IP")
                    if ip_api: return str(ip_api)
                    # 2. Buscar en tvs el que sea sei800tc1 o se llame Deco
                    tvs = data.get("tvs", [])
                    if isinstance(tvs, list):
                        for tv in tvs:
                            if isinstance(tv, dict):
                                if tv.get("type") == "sei800tc1" or "deco" in str(tv.get("name", "")).lower():
                                    return str(tv.get("ip"))
            except Exception: pass
    return "0.0.0.0" # Placeholder genérico

# Configuración dinámica
BASE_DIR: str = os.path.dirname(os.path.abspath(__file__))
# Los certificados suelen estar en la carpeta del deco, buscamos en la repo
CERT_PATH: str = os.path.join(BASE_DIR, "../../../Decos/Telecentro/sei800tc1/cert.pem")
KEY_PATH: str = os.path.join(BASE_DIR, "../../../Decos/Telecentro/sei800tc1/key.pem")

# Fallback si el script se movió
if not os.path.exists(CERT_PATH):
    CERT_PATH = os.path.join(BASE_DIR, "cert.pem")
    KEY_PATH = os.path.join(BASE_DIR, "key.pem")

DECO_IP: str = load_deco_ip()

async def send_deco_command(command_type: str, value: Any = None) -> bool:
    """
    Controlador universal para el Deco Telecentro
    """
    if not AndroidTVRemote:
        print("❌ Error: androidtvremote2 no está instalado.")
        return False

    if not os.path.exists(CERT_PATH):
        print(f"❌ Error: No se encuentran certificados en {CERT_PATH}")
        return False

    client = AndroidTVRemote( # type: ignore
        client_name="Fina Ergen", 
        certfile=CERT_PATH,
        keyfile=KEY_PATH,
        host=DECO_IP
    )

    try:
        await client.async_connect() # type: ignore
        # Pequeña espera para asegurar que el protocolo esté listo
        await asyncio.sleep(0.5)

        if command_type == "key":
            client.send_key_command(value) # type: ignore
        
        elif command_type == "channel":
            # Para canales, enviamos los dígitos uno a uno
            digits = str(value)
            for d in digits:
                # Mapeo de dígito a KEYCODE_0-9 (7-16)
                if d.isdigit():
                    keycode = int(d) + 7
                    client.send_key_command(keycode) # type: ignore
                    await asyncio.sleep(0.3)
            # Confirmar con Enter
            client.send_key_command(66) # type: ignore

        elif command_type == "volume":
            if value == "up":
                client.send_key_command("VOLUME_UP") # type: ignore
            elif value == "down":
                client.send_key_command("VOLUME_DOWN") # type: ignore
            elif value == "mute":
                client.send_key_command("VOLUME_MUTE") # type: ignore

        elif command_type == "navigate_tv":
            # Secuencia para ir a TV en Vivo desde Home
            client.send_key_command("HOME") # type: ignore
            await asyncio.sleep(2)
            client.send_key_command("DPAD_RIGHT") # type: ignore
            await asyncio.sleep(0.5)
            client.send_key_command("DPAD_CENTER") # type: ignore

        return True
    except Exception as e:
        print(f"Error Deco: {e}")
        return False
    finally:
        try:
            client.disconnect() # type: ignore
        except Exception:
            pass
    return False

def main() -> None:
    if len(sys.argv) < 2:
        print("Uso: python3 control_deco.py <comando> [valor]")
        sys.exit(1)
    
    cmd_arg = sys.argv[1]
    val_arg = sys.argv[2] if len(sys.argv) > 2 else None
    
    asyncio.run(send_deco_command(cmd_arg, val_arg))

if __name__ == "__main__":
    main()
