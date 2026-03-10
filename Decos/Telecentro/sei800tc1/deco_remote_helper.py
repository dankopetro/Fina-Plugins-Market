import asyncio
import os
import sys
from typing import Optional, Any, Union
from androidtvremote2 import AndroidTVRemote # type: ignore

# Rutas absolutas para los certificados en la carpeta del modelo
BASE_DIR: str = os.path.dirname(os.path.abspath(__file__))
CERT_PATH: str = os.path.join(BASE_DIR, "cert.pem")
KEY_PATH: str = os.path.join(BASE_DIR, "key.pem")

async def check_if_on(ip: str) -> bool:
    """Verifica si el dispositivo está encendido vía AndroidTVRemote2"""
    client: Optional[AndroidTVRemote] = None
    try:
        client = AndroidTVRemote(client_name="Fina Ergen", certfile=CERT_PATH, keyfile=KEY_PATH, host=ip)
        await client.async_connect() # type: ignore
        return bool(client.is_on) # type: ignore
    except Exception:
        return False
    finally:
        if client:
            try:
                client.disconnect() # type: ignore
            except Exception:
                pass
    return False

async def send_command(ip: str, command_type: str, value: Optional[Union[str, int]] = None) -> bool:
    """Envía comandos (teclas, encendido, canales, volumen) al deco"""
    client: Optional[AndroidTVRemote] = None
    try:
        client = AndroidTVRemote(
            client_name="Fina Ergen", 
            certfile=CERT_PATH,
            keyfile=KEY_PATH,
            host=ip
        )
        await client.async_connect() # type: ignore
        await asyncio.sleep(0.5)

        if not client:
            return False

        if command_type == "key":
            client.send_key_command(str(value)) # type: ignore
        elif command_type == "power_on":
            if not client.is_on: # type: ignore
                client.send_key_command("POWER") # type: ignore
        elif command_type == "power_off":
            if client.is_on: # type: ignore
                client.send_key_command("POWER") # type: ignore
        elif command_type == "channel" and value is not None:
            # Forzamos string para iterar dígitos
            for d in str(value):
                if d.isdigit():
                    client.send_key_command(int(d) + 7) # type: ignore # KEYCODE_0 a KEYCODE_9
                elif d == ".":
                    client.send_key_command(56) # type: ignore # KEYCODE_PERIOD
                elif d == "-":
                    client.send_key_command(69) # type: ignore # KEYCODE_MINUS
                await asyncio.sleep(0.1)
            client.send_key_command(66) # type: ignore # ENTER
        elif command_type == "volume":
            client.send_key_command(f"VOLUME_{str(value).upper()}") # type: ignore
        
        return True
    except Exception as e:
        print(f"Error Deco: {e}")
        return False
    finally:
        if client:
            try:
                client.disconnect() # type: ignore
            except Exception:
                pass
    return False
