
import asyncio
import os
import sys
from androidtvremote2 import AndroidTVRemote

# Rutas absolutas para los certificados en la carpeta del modelo
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CERT_PATH = os.path.join(BASE_DIR, "cert.pem")
KEY_PATH = os.path.join(BASE_DIR, "key.pem")

async def check_if_on(ip):
    client = AndroidTVRemote(client_name="Fina Ergen", certfile=CERT_PATH, keyfile=KEY_PATH, host=ip)
    try:
        await client.async_connect()
        return client.is_on
    except:
        return False
    finally:
        client.disconnect()

async def send_command(ip, command_type, value=None):
    client = AndroidTVRemote(
        client_name="Fina Ergen", 
        certfile=CERT_PATH,
        keyfile=KEY_PATH,
        host=ip
    )
    try:
        await client.async_connect()
        await asyncio.sleep(0.5)

        if command_type == "key":
            client.send_key_command(value)
        elif command_type == "power_on":
            if not client.is_on:
                client.send_key_command("POWER")
        elif command_type == "power_off":
            if client.is_on:
                client.send_key_command("POWER")
        elif command_type == "channel":
            # Forzamos string para iterar dígitos
            for d in str(value):
                if d.isdigit():
                    client.send_key_command(int(d) + 7) # KEYCODE_0 a KEYCODE_9
                elif d == ".":
                    client.send_key_command(56) # KEYCODE_PERIOD
                elif d == "-":
                    client.send_key_command(69) # KEYCODE_MINUS
                await asyncio.sleep(0.1) # Reducido de 0.3 a 0.1 para más velocidad
            client.send_key_command(66) # ENTER
        elif command_type == "volume":
            client.send_key_command(f"VOLUME_{value.upper()}")
        
        return True
    except Exception as e:
        print(f"Error Deco: {e}")
        return False
    finally:
        client.disconnect()
