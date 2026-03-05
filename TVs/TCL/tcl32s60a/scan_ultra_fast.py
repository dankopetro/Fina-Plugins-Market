#!/usr/bin/env python3
"""
Script ultra rápido para escanear canales con entrada directa de números
Optimizado para manejo de errores y cancelación dinámica
"""

import subprocess
import json
import time
import os
import sys
import argparse

CANCEL_FILE = "/tmp/fina_cancel_scan"

def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ip", help="IP de la TV", default=None)
    return parser.parse_args()

def check_cancel():
    if os.path.exists(CANCEL_FILE):
        print("\n🛑 CANCELACIÓN DETECTADA 🛑")
        try:
            os.remove(CANCEL_FILE)
        except:
            pass
        return True
    return False

def input_channel_direct(ip, channel_number):
    """Ingresar canal directamente"""
    try:
        cmd = f"input text '{channel_number}'"
        # Timeout corto para no trabar el script si la TV no responde
        subprocess.run(['adb', '-s', f'{ip}:5555', 'shell', cmd], 
                      capture_output=True, text=True, timeout=1.5)
        time.sleep(0.1)
        return True
    except subprocess.TimeoutExpired:
        print(f"⚠️ Timeout en canal {channel_number}")
        return False
    except Exception as e:
        print(f"❌ Error ADB: {e}")
        return False

def scan_ultra_fast(ip):
    """Escaneo ultra rápido desde 80.1"""
    print(f"⚡ Iniciando escaneo en {ip}...")
    
    channels_found = {}
    
    # Nombres predefinidos
    channel_names = {
        '80.1': 'Somos La Plata', '80.2': 'Canal de la Ciudad', '80.3': 'Metro',
        '80.4': 'América TV', '80.5': 'Telefe', '80.6': 'TV Pública',
        '80.7': 'El Trece', '80.8': 'El Nueve', '80.9': 'Magazine',
        '81.1': 'TN', '81.2': 'La Nacion+', '81.3': 'C5N', '81.4': 'Crónica TV',
        '81.5': 'Canal 26', '81.6': 'A24', '81.7': 'Ciudad Magazine', '81.8': 'Net TV',
        '81.9': 'Bravo',
        '82.1': 'Bravo', '82.2': 'Argentina 12', '82.3': 'KZO', '82.4': 'TyC Sports',
        '82.5': 'ESPN 2', '82.6': 'ESPN', '82.7': 'ESPN 3', '82.8': 'ESPN 4',
        '82.9': 'Fox Sports Premium',
        '83.1': 'Fox Sports', '83.2': 'Fox Sports 2', '83.3': 'Fox Sports 3',
        '83.4': 'Disney Channel', '83.5': 'Nickelodeon', '83.6': 'Cartoonito',
        '83.7': 'Discovery Kids', '83.8': 'Disney Junior', '83.9': 'Paka Paka',
        '84.1': 'Paka Paka', '84.2': 'Cartoon Network', '84.3': 'Space',
        '84.4': 'Cinemax', '84.5': 'Paramount', '84.6': 'Volver', '84.7': 'Info Flow',
        '84.8': 'Cinecanal', '84.9': 'TNT',
        '85.1': 'TNT', '85.2': 'TNT Series', '85.3': 'FX', '85.4': 'Star Channel',
        '85.5': 'Sony Channel', '85.6': 'Warner Channel', '85.7': 'Universal Channel',
        '85.8': 'AXN', '85.9': 'A&E',
        '86.1': 'A&E', '86.2': 'TNT Novelas', '86.3': 'TCM', '86.4': 'AMC',
        '86.5': 'Discovery ID', '86.6': 'Comedy Central', '86.7': 'Cine Ar',
        '86.8': 'Studio Universal', '86.9': 'El Gourmet',
        '87.1': 'El Gourmet', '87.2': 'El Garage TV', '87.3': 'Discovery H&H',
        '87.4': 'Encuentro', '87.5': 'National Geographic', '87.6': 'Discovery Channel',
        '87.7': 'Animal Planet', '87.8': 'History Channel', '87.9': 'Canal A',
        '88.1': 'Canal A', '88.2': 'History 2', '88.3': 'E!', '88.4': 'Quiero Música',
        '88.5': 'MTV', '88.6': 'Telemundo', '88.7': 'TVE', '88.8': 'RAI',
        '88.9': 'Estrellas',
        '89.1': 'Estrellas', '89.2': 'DeporTV', '89.3': 'CNN en Español',
        '89.4': 'Lifetime', '89.5': 'TLC', '89.6': 'Canal Rural',
        '89.7': 'Eventos 2', '89.8': 'Eventos HD', '89.9': 'Glitz'
    }
    
    # Iniciar app de TV
    try:
        subprocess.run(['adb', '-s', f'{ip}:5555', 'shell', 'am', 'start', '-n', 'com.tcl.tv/.TVActivity'], 
                      capture_output=True, text=True, timeout=5)
    except:
        print("❌ Error al iniciar app de TV")
        return {}

    time.sleep(1)
    
    try:
        # Escanear rangos
        for main_val in range(80, 90):
            if check_cancel(): return {} # Abortar si hay flag de cancelación
            
            for decimal in range(1, 10):
                if check_cancel(): return {}
                
                channel_num = f"{main_val}.{decimal}"
                
                # Intentar entrada directa
                success = input_channel_direct(ip, channel_num)
                
                if success:
                    channel_name = channel_names.get(channel_num, f'Canal {channel_num}')
                    channels_found[channel_name.lower()] = channel_num
                    print(f"⚡ {channel_num} → {channel_name}")
                
            print(f"✅ Rango {main_val}.x completado")
            
    except KeyboardInterrupt:
        print(f"\n⏹️ Escaneo detenido por el usuario")
    
    return channels_found

def main():
    args = get_args()
    ip = args.ip
    
    if not ip:
        print("❌ Error: No se proporcionó IP")
        return

    # Limpiar flag de cancelación previo
    if os.path.exists(CANCEL_FILE):
        os.remove(CANCEL_FILE)

    print(f"📡 TV: {ip} | Escaneo Ultra Fast")
    
    channels_found = scan_ultra_fast(ip)
    
    # Solo guardar si el escaneo terminó o no fue cancelado
    if channels_found:
        # Priorizar Carpeta de Usuario
        config_dir = os.path.expanduser("~/.config/Fina")
        output_file = os.path.join(config_dir, "channels.json")
        
        # Fallback si no existe la carpeta (aunque main.py la crea)
        if not os.path.exists(config_dir):
            output_file = os.path.join(".", "config", "channels.json")
        
        try:
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(channels_found, f, indent=4, ensure_ascii=False)
            print(f"✅ ÉXITO: {len(channels_found)} canales guardados.")
        except Exception as e:
            print(f"❌ Error guardando json: {e}")
    else:
        print("❌ Escaneo cancelado o sin resultados. No se guardó nada.")

if __name__ == "__main__":
    main()
