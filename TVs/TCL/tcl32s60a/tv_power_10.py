import subprocess
import sys
import time
import socket

TARGET_IP = '192.168.0.10'
TARGET_MAC = '34:51:80:f9:86:4a'

def wake_on_lan(mac_address):
    """Envía un paquete mágico WoL a la dirección MAC especificada"""
    try:
        # Convertir MAC formato XX:XX:XX... a bytes
        mac_bytes = bytes.fromhex(mac_address.replace(':', '').replace('-', ''))
        # Crear el paquete mágico: 6 bytes de 0xFF seguidos de 16 repeticiones de la MAC
        magic_packet = b'\xff' * 6 + mac_bytes * 16
        
        # Enviar vía broadcast
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.sendto(magic_packet, ('<broadcast>', 9))
            
        print(f'⚡ Paquete Wake-on-LAN enviado a {mac_address}')
        return True
    except Exception as e:
        print(f'⚠ Warning: No se pudo enviar WoL: {e}')
        return False

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

def connect_with_retry_loop(ip):
    """
    Intenta conectar a la IP.
    Realiza intentos durante 30 segundos. Si falla, reinicia el ciclo.
    """
    while True:
        print(f'\n--- Iniciando ciclo de conexión (30s) para {ip} ---')
        
        # Intentar despertar la TV vía WoL al inicio del ciclo
        wake_on_lan(TARGET_MAC)
        
        cycle_start_time = time.time()
        
        # Mantener este ciclo por 30 segundos
        while time.time() - cycle_start_time < 30:
            try:
                print(f'Intentando adb connect {ip}...')
                # Intentar conexión con timeout corto para no bloquear
                proc = subprocess.run(
                    ['adb', 'connect', ip],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                output = proc.stdout.strip()
                print(f"Resultado connect: {output}")
                
                 # Verificar si está conectado realmente y operativo
                is_connected = check_device_connection(ip)
                
                if is_connected:
                    print(f'✓ Conectado exitosamente a {ip}')
                    return True
                
                # AUTOCURACIÓN: Si ADB dice "already connected" pero el check falló (está offline),
                # forzamos la desconexión para limpiar el estado y reintentamos.
                if 'already connected' in output and not is_connected:
                    print(f'⚠ Estado inconsistente (already connected + offline). Forzando desconexión de {ip}...')
                    subprocess.run(['adb', 'disconnect', ip], capture_output=True, timeout=3)
                    time.sleep(1)
                    continue
                
                # Si no conectó, esperar brevemente antes del siguiente intento
                time.sleep(2)
                
            except subprocess.TimeoutExpired:
                print('⚠ Timeout en comando adb connect')
            except Exception as e:
                print(f'⚠ Error en intento de conexión: {e}')
                time.sleep(2)
        
        print('⚠ Ciclo de 30 segundos finalizado sin éxito. Reiniciando operación...')
        time.sleep(1) # Breve pausa antes de reiniciar el ciclo grande

def send_power_command(ip):
    """Envía el comando de encendido a la TV"""
    try:
        print(f'Enviando comando de encendido a {ip}...')
        result = subprocess.run(
            ['adb', '-s', f'{ip}:5555', 'shell', 'input', 'keyevent', 'KEYCODE_POWER'],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0:
            print(f'✓ Comando de encendido enviado exitosamente a {ip}')
            return True
        else:
            print(f'✗ Error al enviar comando: {result.stderr}')
            # A veces adb devuelve error pero funciona, depende del error
            return False
            
    except subprocess.TimeoutExpired:
        # El timeout es normal, el comando puede haberse ejecutado
        print(f'⚠ Comando enviado (timeout esperado)')
        return True
    except Exception as e:
        print(f'✗ Error al enviar comando: {e}')
        return False

def main():
    print('=' * 60)
    print(f'TV POWER SCRIPT - TARGET: {TARGET_IP}')
    print('No se reiniciará el servidor ADB.')
    print('=' * 60)
    
    try:
        if connect_with_retry_loop(TARGET_IP):
            # Una vez conectado, enviamos power
            # Esperar un momento para estabilizar
            time.sleep(1)
            send_power_command(TARGET_IP)
            sys.exit(0)
    except KeyboardInterrupt:
        print('\n\nOperación cancelada por el usuario')
        sys.exit(1)
    except Exception as e:
        print(f'\n✗ Error inesperado: {e}')
        sys.exit(1)

if __name__ == '__main__':
    main()
