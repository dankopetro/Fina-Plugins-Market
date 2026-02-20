
import asyncio
import sys
import os
from androidtvremote2 import AndroidTVRemote

# Configuración fija del Deco
DECO_IP = "192.168.0.9"
CERT_PATH = "./iot/cert.pem"
KEY_PATH = "./iot/key.pem"

async def send_deco_command(command_type, value=None):
    """
    Controlador universal para el Deco Telecentro
    command_type: 'key', 'channel', 'app', 'volume'
    """
    client = AndroidTVRemote(
        client_name="Fina Ergen", 
        certfile=CERT_PATH,
        keyfile=KEY_PATH,
        host=DECO_IP
    )

    try:
        await client.async_connect()
        # Pequeña espera para asegurar que el protocolo esté listo
        await asyncio.sleep(0.5)

        if command_type == "key":
            client.send_key_command(value)
        
        elif command_type == "channel":
            # Para canales, enviamos los dígitos uno a uno
            digits = str(value)
            for d in digits:
                # Mapeo de dígito a KEYCODE_0-9 (7-16)
                keycode = int(d) + 7
                client.send_key_command(keycode)
                await asyncio.sleep(0.3)
            # Confirmar con Enter
            client.send_key_command(66)

        elif command_type == "volume":
            if value == "up":
                client.send_key_command("VOLUME_UP")
            elif value == "down":
                client.send_key_command("VOLUME_DOWN")
            elif value == "mute":
                client.send_key_command("VOLUME_MUTE")

        elif command_type == "navigate_tv":
            # Secuencia para ir a TV en Vivo desde Home
            client.send_key_command("HOME")
            await asyncio.sleep(2)
            client.send_key_command("DPAD_RIGHT")
            await asyncio.sleep(0.5)
            client.send_key_command("DPAD_CENTER")

        return True
    except Exception as e:
        print(f"Error Deco: {e}")
        return False
    finally:
        client.disconnect()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python3 control_deco.py <comando> [valor]")
        sys.exit(1)
    
    cmd = sys.argv[1]
    val = sys.argv[2] if len(sys.argv) > 2 else None
    
    asyncio.run(send_deco_command(cmd, val))
