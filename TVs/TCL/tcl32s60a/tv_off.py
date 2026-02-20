import subprocess
import sys
import time
import argparse
import os
import json

# Ajustar ruta al proyecto
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def load_ips_from_settings():
    """Carga IPs desde la configuración"""
    default_ips = ['192.168.0.11', '192.168.0.10']
    
    paths = [
        os.path.join(PROJECT_ROOT, "config", "settings.json")
    ]
    
    for p in paths:
        if os.path.exists(p):
            try:
                with open(p, "r") as f:
                    data = json.load(f)
                    tvs = data.get("tvs", [])
                    if isinstance(tvs, dict):
                         return [v['ip'] for k, v in tvs.items() if v.get('enabled', True) and 'ip' in v]
                    elif isinstance(tvs, list):
                         return [t['ip'] for t in tvs if t.get('enabled', True) and 'ip' in t]
            except: pass
            
    return default_ips

def check_device_connection(ip):
    """Verifica si el dispositivo está conectado y responde"""
    try:
        result = subprocess.run(
            ['adb', 'devices'],
            capture_output=True,
            text=True,
            timeout=3
        )
        # Buscar la IP en la lista de dispositivos conectados
        for line in result.stdout.split('\n'):
            if ip in line and 'device' in line and 'offline' not in line:
                return True
        return False
    except Exception as e:
        print(f'Error verificando dispositivo: {e}')
        return False

def connect_to_tv(ip):
    """Intenta conectarse a la TV via ADB"""
    try:
        print(f'Intentando conectar a {ip}...')
        result = subprocess.run(
            ['adb', 'connect', ip],
            capture_output=True,
            text=True,
            timeout=10
        )
        print(result.stdout.strip())
        
        # Esperar un momento para que se establezca la conexión
        time.sleep(2)
        
        # Verificar si la conexión fue exitosa
        if check_device_connection(ip):
            print(f'✓ Conectado exitosamente a {ip}')
            return True
        else:
            print(f'✗ No se pudo conectar a {ip}')
            return False
            
    except subprocess.TimeoutExpired:
        print(f'✗ Timeout al conectar a {ip}')
        return False
    except Exception as e:
        print(f'✗ Error al conectar a {ip}: {e}')
        return False

def send_sleep_command(ip):
    """Envía el comando de apagado a la TV"""
    try:
        print(f'Enviando comando de apagado a {ip}...')
        result = subprocess.run(
            ['adb', '-s', f'{ip}:5555', 'shell', 'input', 'keyevent', 'KEYCODE_SLEEP'],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0:
            print(f'✓ Comando de apagado enviado exitosamente a {ip}')
            return True
        else:
            print(f'✗ Error al enviar comando: {result.stderr}')
            return False
            
    except subprocess.TimeoutExpired:
        # El timeout es normal, el comando puede haberse ejecutado
        print(f'⚠ Comando enviado (timeout esperado)')
        return True
    except Exception as e:
        print(f'✗ Error al enviar comando: {e}')
        return False

def disconnect_from_tv(ip):
    """Desconecta de la TV"""
    try:
        print(f'Desconectando de {ip}...')
        result = subprocess.run(
            ['adb', 'disconnect', ip],
            capture_output=True,
            text=True,
            timeout=3
        )
        print(result.stdout.strip())
    except Exception as e:
        print(f'Error al desconectar: {e}')

def restart_adb_and_connect(possible_ips):
    """Reinicia el servidor ADB e intenta conectar a todas las IPs"""
    print('\n🔄 Reiniciando servidor ADB...')
    try:
        # Matar el servidor ADB
        subprocess.run(['adb', 'kill-server'], capture_output=True, timeout=5)
        time.sleep(1)
        
        # Iniciar el servidor ADB
        subprocess.run(['adb', 'start-server'], capture_output=True, timeout=5)
        time.sleep(2)
        
        print('✓ Servidor ADB reiniciado')
        
        # Intentar conectar a todas las IPs
        for ip in possible_ips:
            print(f'Intentando conectar a {ip}...')
            try:
                result = subprocess.run(
                    ['adb', 'connect', ip],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                print(result.stdout.strip())
                time.sleep(2)
            except Exception as e:
                print(f'Error conectando a {ip}: {e}')
        
        # Verificar qué dispositivos están conectados
        result = subprocess.run(['adb', 'devices'], capture_output=True, text=True, timeout=3)
        print('\nDispositivos conectados:')
        print(result.stdout)
        
        return True
    except Exception as e:
        print(f'✗ Error reiniciando ADB: {e}')
        return False

def turn_off_android_tv(possible_ips):
    """Intenta apagar la TV probando múltiples IPs"""
    print('=' * 60)
    print('APAGANDO ANDROID TV')
    print('=' * 60)
    
    # Primer intento: conexión normal
    for ip in possible_ips:
        print(f'\n--- Probando IP: {ip} ---')
        
        # Primero verificar si ya está conectado
        if check_device_connection(ip):
            print(f'✓ Ya conectado a {ip}')
            if send_sleep_command(ip):
                disconnect_from_tv(ip)
                print(f'\n✓ TV apagada exitosamente usando {ip}')
                return True
        else:
            # Intentar conectar
            if connect_to_tv(ip):
                if send_sleep_command(ip):
                    disconnect_from_tv(ip)
                    print(f'\n✓ TV apagada exitosamente usando {ip}')
                    return True
    
    # Segundo intento: reiniciar ADB y probar de nuevo
    print('\n⚠ No se pudo conectar con el método normal')
    print('Intentando reiniciar servidor ADB...')
    
    if restart_adb_and_connect(possible_ips):
        # Intentar de nuevo después del reinicio
        for ip in possible_ips:
            print(f'\n--- Reintentando IP: {ip} ---')
            if check_device_connection(ip):
                print(f'✓ Conectado a {ip}')
                if send_sleep_command(ip):
                    disconnect_from_tv(ip)
                    print(f'\n✓ TV apagada exitosamente usando {ip}')
                    return True
    
    print('\n✗ No se pudo apagar la TV con ninguna IP')
    return False

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Turn off Android TV via ADB')
    parser.add_argument('--ip', type=str, help='IP address of the TV')
    args = parser.parse_args()

    if args.ip:
        # Si se especifica IP, SOLO intentamos esa
        tv_ips = [args.ip]
        print(f"Objetivo específico: {args.ip}")
    else:
        # Fallback a lista hardcodeada o cargar de settings
        tv_ips = load_ips_from_settings()
        if not tv_ips:
            tv_ips = ['192.168.0.11', '192.168.0.10']
    
    try:
        success = turn_off_android_tv(tv_ips)
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print('\n\nOperación cancelada por el usuario')
        sys.exit(1)
    except Exception as e:
        print(f'\n✗ Error inesperado: {e}')
        # Loguear error para diagnóstico
        import traceback
        traceback.print_exc()
        sys.exit(1)
