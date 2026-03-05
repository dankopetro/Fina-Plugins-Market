#!/usr/bin/env python3
"""
Script ultra rápido para escanear canales con entrada directa de números
"""

import subprocess
import json
import time
import os

def get_tv_ip():
    """Obtener IP de TV conectada"""
    tv_ips = ['192.168.0.11', '192.168.0.10']
    for ip in tv_ips:
        try:
            result = subprocess.run(['adb', '-s', f'{ip}:5555', 'shell', 'echo', 'test'], 
                                  capture_output=True, text=True, timeout=3)
            if result.returncode == 0:
                return ip
        except:
            continue
    return None

def input_channel_direct(ip, channel_number):
    """Ingresar canal directamente sin pausas"""
    # Usar input text para mayor velocidad
    cmd = f"input text '{channel_number}'"
    subprocess.run(['adb', '-s', f'{ip}:5555', 'shell', cmd], 
                  capture_output=True, text=True, timeout=2)
    time.sleep(0.2)  # Mínima pausa
    return True

def scan_ultra_fast(ip):
    """Escaneo ultra rápido desde 80.1"""
    print("⚡ Escaneo ULTRA RÁPIDO (80.1 → 99.9)")
    print("   Velocidad máxima, sin verificación de señal\n")
    
    channels_found = {}
    
    # Nombres predefinidos completos
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
    subprocess.run(['adb', '-s', f'{ip}:5555', 'shell', 'am', 'start', '-n', 'com.tcl.tv/.TVActivity'], 
                  capture_output=True, text=True, timeout=5)
    time.sleep(2)
    
    try:
        # Escanear desde 80.1 hasta 89.9
        for main in range(80, 90):
            for decimal in range(1, 10):
                channel_num = f"{main}.{decimal}"
                
                # Ingresar canal ultra rápido
                input_channel_direct(ip, channel_num)
                
                # Obtener nombre y guardar
                channel_name = channel_names.get(channel_num, f'Canal {channel_num}')
                channels_found[channel_name.lower()] = channel_num
                
                # Mostrar progreso
                print(f"⚡ {channel_num} → {channel_name}")
                
                # Mínima pausa
                time.sleep(0.1)
            
            print(f"✅ Rango {main}.x completado\n")
            
    except KeyboardInterrupt:
        print(f"\n⏹️ Escaneo detenido")
    
    return channels_found

def main():
    """Función principal"""
    print("⚡ Escaneo ULTRA RÁPIDO de Canales TCL")
    print("=" * 50)
    
    ip = get_tv_ip()
    if not ip:
        print("❌ No hay TV conectada vía ADB")
        return
    
    print(f"📡 TV conectada: {ip}")
    print("🚀 Velocidad: Máxima (0.1s por canal)")
    
    # Escanear canales
    channels_found = scan_ultra_fast(ip)
    
    # Guardar resultados
    if channels_found:
        with open('test/digital.json', 'w', encoding='utf-8') as f:
            json.dump(channels_found, f, indent=4, ensure_ascii=False)
        
        print(f"\n✅ Guardados {len(channels_found)} canales en test/digital.json")
        print("\n📋 Total de canales procesados:")
        print(f"   Principales: {len([c for c in channels_found.keys() if not c.startswith('canal ')])}")
        print(f"   Genéricos: {len([c for c in channels_found.keys() if c.startswith('canal ')])}")
    else:
        print("\n❌ No se encontraron canales")

if __name__ == "__main__":
    main()
