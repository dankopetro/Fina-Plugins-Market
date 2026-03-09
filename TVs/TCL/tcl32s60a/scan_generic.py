#!/usr/bin/env python3
"""
Script ultra rápido para escanear canales con entrada directa de números
"""

import subprocess
import json
import time
import os
import sys
import argparse
from pathlib import Path
from typing import Optional, Dict, List, Any, Tuple

def get_config_dir() -> str:
    """Obtiene el directorio de configuración de Fina siguiendo estándares XDG"""
    xdg_config = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config:
        return str(xdg_config)
    return str(Path.home() / ".config" / "Fina")

def get_tv_ip() -> Optional[str]:
    """Obtiene la IP de la primera TV disponible en la configuración de Fina"""
    config_dir = get_config_dir()
    paths: List[str] = [
        os.path.join(config_dir, "settings.json"),
        os.path.join(str(Path(__file__).parents[4]), "config", "settings.json")
    ]
    
    for p in paths:
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data: Dict[str, Any] = json.load(f)
                    tvs: List[Dict[str, Any]] = data.get("tvs", [])
                    for tv in tvs:
                        ip = tv.get("ip")
                        if ip:
                            # Verificar si responde rápido
                            try:
                                target = f"{ip}:5555" if ":" not in str(ip) else str(ip)
                                res = subprocess.run(["adb", "connect", target], capture_output=True, timeout=2) # type: ignore
                                if res.returncode == 0:
                                    return str(ip)
                            except Exception:
                                continue
            except Exception:
                pass
    return None

def input_channel_direct(ip: str, channel_number: str) -> bool:
    """Ingresa un número de canal directamente vía ADB text input"""
    target = f"{ip}:5555" if ":" not in ip else ip
    cmd: str = f"input text '{channel_number}'"
    try:
        subprocess.run(["adb", "-s", target, "shell", cmd], capture_output=True, timeout=2) # type: ignore
        return True
    except Exception:
        return False

def scan_ultra_fast(ip: str) -> Dict[str, str]:
    """Realiza un barrido ultra rápido de canales predefinidos"""
    print(f"⚡ Iniciando escaneo en {ip} (80.1 → 89.9)...")
    
    channels_found: Dict[str, str] = {}
    
    # Mapeo de canales conocidos para autocompletar nombres
    channel_names: Dict[str, str] = {
        '80.1': 'Somos La Plata', '80.2': 'Canal de la Ciudad', '80.3': 'Metro',
        '80.4': 'América TV', '80.5': 'Telefe', '80.6': 'TV Pública',
        '80.7': 'El Trece', '80.8': 'El Nueve', '80.9': 'Magazine',
        '81.1': 'TN', '81.2': 'La Nacion+', '81.3': 'C5N', '81.4': 'Crónica TV',
        '81.5': 'Canal 26', '81.6': 'A24', '81.7': 'Ciudad Magazine', '81.8': 'Net TV',
        '81.9': 'Bravo', '82.4': 'TyC Sports', '82.5': 'ESPN 2', '82.6': 'ESPN',
        '83.1': 'Fox Sports', '84.2': 'Cartoon Network', '84.4': 'Cinemax',
        '85.4': 'Star Channel', '86.7': 'Cine Ar', '87.4': 'Encuentro'
    }
    
    target = f"{ip}:5555" if ":" not in ip else ip
    
    # Iniciar app de TV
    try:
        subprocess.run(["adb", "-s", target, "shell", "am", "start", "-n", "com.google.android.tv.framework/com.android.tv.MainActivity"], # type: ignore
                      capture_output=True, timeout=5)
        time.sleep(2)
    except Exception:
        pass

    try:
        for main_idx in range(80, 90):
            for decimal in range(1, 10):
                channel_num: str = f"{main_idx}.{decimal}"
                input_channel_direct(ip, channel_num)
                
                name: str = channel_names.get(channel_num, f"Canal {channel_num}")
                channels_found[name.lower()] = channel_num
                
                print(f"→ {channel_num}: {name}")
                time.sleep(0.1)
                
    except KeyboardInterrupt:
        print("\n⏹ Escaneo interrumpido.")
    
    return channels_found

def main() -> None:
    """Función principal de ejecución"""
    parser = argparse.ArgumentParser(description="Escaneo genérico de canales para TV TCL")
    parser.add_argument("--ip", help="IP de la TV (opcional, busca en config si no se provee)")
    args = parser.parse_args()

    print("⚡ Fina Ergen: Generic Ultra Fast Scan")
    print("=" * 40)

    target_ip: Optional[str] = args.ip if args.ip else get_tv_ip()
    
    if not target_ip:
        print("❌ Error: No se pudo detectar la IP de la TV. Usá --ip.")
        sys.exit(1)

    # Asegurar a los linters que target_ip es str tras el check
    final_ip: str = str(target_ip)
    found: Dict[str, str] = scan_ultra_fast(final_ip)
    
    if found:
        output_file: str = os.path.join(get_config_dir(), "channels.json")
        try:
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(found, f, indent=4, ensure_ascii=False)
            print(f"\n✅ Guardados {len(found)} canales en {output_file}")
        except Exception as e:
            print(f"❌ Error guardando resultados: {e}")
    else:
        print("\n⚠ No se capturaron canales.")

if __name__ == "__main__":
    try:
        main()
    except Exception as fatal:
        print(f"✗ Fatal: {fatal}")
        sys.exit(1)
