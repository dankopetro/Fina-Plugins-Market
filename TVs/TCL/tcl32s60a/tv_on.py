import subprocess
import sys
import time
import socket
import os
import json
import argparse

# RUTA AL PROYECTO (Dinámica y Resiliente)
script_dir = os.path.dirname(os.path.abspath(__file__))
# Fallback para la máquina del usuario
USER_HOME = os.path.expanduser("~")
PROJECT_ROOT = os.path.join(USER_HOME, "Descargas/Fina-Ergen")
# Intentar detectar si estamos dentro de la repo
if "Descargas/Fina-Ergen/plugins" in script_dir:
    PROJECT_ROOT = script_dir.split("/plugins")[0]
elif "Descargas/Fina-Ergen/.local_lab" in script_dir:
    PROJECT_ROOT = script_dir.split("/.local_lab")[0]

sys.path.append(PROJECT_ROOT)

def wake_on_lan(macaddress, ip_hint=None):
    """Envia un paquete Magic Packet para despertar la TV"""
    if not macaddress:
        return False
    
    # Normalizar MAC
    if len(macaddress) == 12:
        pass
    elif len(macaddress) == 12 + 5:
        sep = macaddress[2]
        macaddress = macaddress.replace(sep, '')
    else:
        return False

    # Crear el magic packet
    data = b'f' * 12 + (bytes.fromhex(macaddress) * 16)
    
    # Enviar por broadcast
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    
    try:
        # Enviar a broadcast general y al hint si existe
        sock.sendto(data, ('255.255.255.255', 9))
        if ip_hint:
            sock.sendto(data, (ip_hint, 9))
        return True
    except Exception as e:
        print(f"Error enviando WoL: {e}")
        return False
    finally:
        sock.close()

def check_device_connection(ip):
    """Verifica si el dispositivo está conectado via ADB"""
    try:
        result = subprocess.run(
            ['adb', 'devices'],
            capture_output=True,
            text=True,
            timeout=3
        )
        for line in result.stdout.split('\n'):
            if ip in line and 'device' in line and 'offline' not in line:
                return True
        return False
    except:
        return False

def send_power_and_exit(ip):
    """Asegura que la TV esté encendida y termina"""
    print(f"⚡ Enviando comando de encendido a {ip}...")
    try:
        # KEYCODE_WAKEUP (224) - Despierta el dispositivo si está en sleep
        # NO enviamos KEYCODE_POWER (26) porque es toggle y si ya despertó, la apaga.
        # WAKEUP debería ser suficiente para la mayoría de Android TVs modernos.
        subprocess.run(['adb', '-s', f'{ip}:5555', 'shell', 'input', 'keyevent', '224'], timeout=3)
        print("✅ Comandos enviados. Cerrando.")
        sys.exit(0)
    except Exception as e:
        print(f"Error enviando comandos: {e}")

def load_targets_from_settings():
    """Carga configuración desde settings.json"""
    default_targets = [
        {"ip": "192.168.0.11", "mac": "38:c8:04:31:17:b0"},
        {"ip": "192.168.0.10", "mac": "34:51:80:f9:86:4a"},
        {"ip": "192.168.0.9",  "mac": "8C:98:06:02:70:4E"}  # Deco Telecentro
    ]
    
    paths = [
        os.path.join(os.path.expanduser("~"), ".config", "Fina", "settings.json"),
        os.path.join(PROJECT_ROOT, "config", "settings.json")
    ]

    for p in paths:
        if os.path.exists(p):
            try:
                with open(p, "r") as f:
                    data = json.load(f)
                    tvs = data.get("tvs", [])
                    if isinstance(tvs, dict):
                       return [v for k, v in tvs.items() if v.get("enabled", True)]
                    elif isinstance(tvs, list):
                        return [t for t in tvs if t.get("enabled", True)]
            except: pass
    
    return default_targets

def connect_loop(specific_target=None):
    """Ciclo principal"""
    print('=' * 60)
    print('TV ON - Modo Inteligente')
    print('=' * 60)
    
    if specific_target:
        targets = [specific_target]
        print(f"🎯 Objetivo único: {specific_target.get('ip', 'Desconocido')}")
    else:
        targets = load_targets_from_settings()
        print(f"📋 Escaneando {len(targets)} objetivos...")
    
    cycle_count = 1
    max_cycles = 3  # Reducido de 10 a 3 para evitar bucles eternos 
    
    while cycle_count <= max_cycles:
        print(f'\n--- Intento #{cycle_count} ---')
        
        if cycle_count == 1:
            for t in targets:
                ip_t = t.get('ip')
                if ip_t:
                    # Intento preventivo de desconexión para limpiar estados zombies
                    try:
                        subprocess.run(['adb', 'disconnect', ip_t], capture_output=True, timeout=2)
                    except: pass

        for target in targets:
            ip = target.get('ip')
            mac = target.get('mac')
            
            if not ip: continue

            # 1. WoL (Para sacarla de sueño profundo si está apagada)
            if mac:
                print(f"○ Enviando WoL a {mac} ({ip})...")
                wake_on_lan(mac, ip_hint=ip)
            
            # 2. Intentar conectar ADB
            print(f"🔌 Intentando conectar ADB a {ip}...")
            try:
                subprocess.run(['adb', 'connect', ip], capture_output=True, timeout=5)
            except subprocess.TimeoutExpired:
                print(f"⚠️ Timeout conectando a {ip}")
                continue
            except Exception as e:
                print(f"⚠️ Error conectando a {ip}: {e}")
                continue

            # 3. Verificar si responde y enviar Power
            if check_device_connection(ip):
                 print(f"✓ {ip} conectado via ADB.")
                 send_power_and_exit(ip) # Esto hace sys.exit si funciona
        
        print("⏳ Esperando respuesta de la red...")
        time.sleep(3)
        cycle_count += 1

    print('\n✗ No se pudo encender la TV.')
    sys.exit(1)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--ip", help="IP específica")
    parser.add_argument("--mac", help="MAC específica")
    args = parser.parse_args()

    target = None
    if args.ip:
        target = {"ip": args.ip, "mac": args.mac}
    
    try:
        connect_loop(target)
    except KeyboardInterrupt:
        sys.exit(1)
