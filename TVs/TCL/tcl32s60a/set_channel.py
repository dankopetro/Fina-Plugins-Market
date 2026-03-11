#!/usr/bin/env python3
"""
set_channel.py — Sintonización de canales en TVs Android (TCL) vía ADB.
Usa búsqueda genérica por glob para soportar cualquier operadora de cable.
"""
import subprocess
import time
import argparse
import sys
import os
import json
import glob
import re
from pathlib import Path
from typing import Optional, Dict, List, Any

# --- Detección dinámica de raíz del proyecto ---
def find_project_root() -> Optional[str]:
    """Busca la raíz del proyecto basándose en marcadores conocidos"""
    curr: Path = Path(__file__).resolve().parent
    for parent in [curr] + list(curr.parents):
        if (parent / "package.json").exists() or (parent / "src" / "App.vue").exists():
            return str(parent)
    return None

PROJECT_ROOT: Optional[str] = find_project_root()

# Mapping de dígitos a Key Events ADB
KEY_MAP_TCL: Dict[str, str] = {
    '0': '7', '1': '8', '2': '9', '3': '10', '4': '11',
    '5': '12', '6': '13', '7': '14', '8': '15', '9': '16',
    '.': '158', '-': '69'
}

def get_provider_from_settings(config_dir: str) -> Optional[str]:
    """Lee el nombre del proveedor de cable/aire configurado en settings.json"""
    candidates: List[str] = [os.path.join(config_dir, "settings.json")]
    if PROJECT_ROOT:
        candidates.append(os.path.join(str(PROJECT_ROOT), "config", "settings.json"))

    for path in candidates:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data: Dict[str, Any] = json.load(f)
                    provider: Any = (
                        data.get("deco", {}).get("provider") or
                        data.get("apis", {}).get("CABLE_PROVIDER")
                    )
                    if provider:
                        return str(provider).lower().strip()
            except Exception:
                pass
    return None

def load_channels() -> Dict[str, str]:
    """
    Carga el mapa de canales (nombre → número) con búsqueda genérica por glob.

    Orden de prioridad:
      1. channels_<proveedor>.json  (del proveedor en settings.json)
      2. channels_*.json            (cualquier operadora, descubierta por glob)
      3. channels.json              (fallback genérico)
    """
    channels: Dict[str, str] = {}

    xdg_config: Optional[str] = os.environ.get("XDG_CONFIG_HOME")
    config_dir: str = str(Path(xdg_config) / "Fina") if xdg_config else str(Path.home() / ".config" / "Fina")

    provider: Optional[str] = get_provider_from_settings(config_dir)
    candidates: List[str] = []

    # 1. Archivo del proveedor configurado explícitamente
    if provider:
        named: str = f"channels_{provider}.json"
        candidates.append(os.path.join(config_dir, named))
        if PROJECT_ROOT:
            candidates.append(os.path.join(str(PROJECT_ROOT), "config", named))

    # 2. Cualquier channels_*.json encontrado por glob
    for found in sorted(glob.glob(os.path.join(config_dir, "channels_*.json"))):
        if found not in candidates:
            candidates.append(found)
    if PROJECT_ROOT:
        for found in sorted(glob.glob(os.path.join(str(PROJECT_ROOT), "config", "channels_*.json"))):
            if found not in candidates:
                candidates.append(found)

    # 3. Fallback genérico
    candidates.append(os.path.join(config_dir, "channels.json"))
    if PROJECT_ROOT:
        candidates.append(os.path.join(str(PROJECT_ROOT), "config", "channels.json"))

    for path in candidates:
        if not os.path.exists(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    for ch in data:
                        if isinstance(ch, dict) and "name" in ch and "number" in ch:
                            key: str = str(ch["name"]).lower().replace(" ", "").strip()
                            channels[key] = str(ch["number"])
                elif isinstance(data, dict):
                    for name, number in data.items():
                        key_d: str = str(name).lower().replace(" ", "").strip()
                        channels[key_d] = str(number)

                if channels:
                    fname: str = os.path.basename(path)
                    detected: str = fname.replace("channels_", "").replace(".json", "").capitalize()
                    label: str = f"proveedor '{detected}'" if "_" in fname else "genérico"
                    print(f"📖 Cargados {len(channels)} canales [{label}] desde {path}")
                    return channels
        except Exception as e:
            print(f"⚠️ Error cargando {path}: {e}")

    return channels

def get_channel_number(query: str, channel_map: Dict[str, str]) -> Optional[str]:
    """Resuelve nombre o número de canal desde el mapa con motor fonético y difuso"""
    # Si ya es un número (con punto o guión incluidos), usarlo directo
    if re.match(r'^[\d\.\-]+$', str(query)):
        return str(query)

    q: str = str(query).lower().replace(" ", "")
    
    # Motor fonético para arreglar errores del micrófono (OCR)
    phonetic_map: Dict[str, str] = {
        "iespien": "espn", "yespien": "espn", "ispen": "espn", "espen": "espn",
        "iestien": "espn", "iepien": "espn", "eiespien": "espn",
        "focs": "fox", "foks": "fox", 
        "teise": "tyc", "teice": "tyc", "teis": "tyc",
        "cartun": "cartoon", "disnei": "disney", 
        "ei yan i": "a&e", "eyane": "a&e", "ayana": "a&e",
        "achiyo": "hbo", "achebeo": "hbo", "achebeó": "hbo",
        "espor": "sports", "esports": "sports"
    }
    
    for k, v in phonetic_map.items():
        if k in str(q):
            q = str(q).replace(k, str(v))

    # Búsqueda exacta primero
    if q in channel_map:
        return str(channel_map[q])
        
    # Búsqueda por contención
    for name, number in channel_map.items():
        if str(q) in str(name) or str(name) in str(q):
            return str(number)

    # Fallback a búsqueda difusa
    import difflib
    matches = difflib.get_close_matches(q, list(channel_map.keys()), n=1, cutoff=0.6)
    if matches:
        matched_key = str(matches[0])
        print(f"🎯 Mapeado fonético/difuso '{query}' -> {matched_key} -> {channel_map[matched_key]}")
        return str(channel_map[matched_key])

    return None

def send_adb_key(ip: str, key_code: str) -> None:
    """Envía una tecla individual por ADB"""
    try:
        cmd: List[str] = ["adb", "-s", f"{ip}:5555", "shell", "input", "keyevent", key_code]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2) # type: ignore
    except Exception:
        pass

def change_channel(ip: str, channel_number: str) -> None:
    """Envía los dígitos del canal por ADB en modo ráfaga y confirma con ENTER"""
    print(f"🚀 Sintonizando canal {channel_number} en {ip}...")

    keycodes: List[str] = [KEY_MAP_TCL[d] for d in str(channel_number) if d in KEY_MAP_TCL]

    if not keycodes:
        print(f"⚠️ No se pudo procesar el número de canal: {channel_number}")
        return

    try:
        cmd: List[str] = ["adb", "-s", f"{ip}:5555", "shell", "input", "keyevent"] + keycodes
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=4) # type: ignore
        time.sleep(0.1)
        send_adb_key(ip, "66")  # KEYCODE_ENTER
        print("✅ Canal enviado con éxito.")
    except Exception as e:
        print(f"❌ Error ADB: {e}")

def main() -> None:
    """Punto de entrada principal"""
    parser = argparse.ArgumentParser(description="Sintonizar canal en TV TCL vía ADB")
    parser.add_argument("--ip", required=True, help="IP de la TV")
    parser.add_argument("--channel", required=True, help="Nombre o número del canal")
    args = parser.parse_args()

    mapping: Dict[str, str] = load_channels()
    target_number: Optional[str] = get_channel_number(str(args.channel), mapping)

    if target_number:
        change_channel(str(args.ip), target_number)
    else:
        print(f"❌ No encontré el canal '{args.channel}' en la lista.")
        sys.exit(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    except Exception as fatal:
        print(f"✗ Fatal: {fatal}")
        sys.exit(1)
