#!/usr/bin/env python3
import asyncio
import sys
import argparse
import os
import json
from pathlib import Path
from typing import Optional, Dict, List, Any

# Agregar el directorio actual al path para importar deco_remote_helper
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
try:
    from deco_remote_helper import send_command # type: ignore
except ImportError:
    # Fallback si falla el import relativo
    from .deco_remote_helper import send_command # type: ignore

def find_project_root() -> Optional[str]:
    """Busca la raíz del proyecto basándose en marcadores conocidos"""
    curr: Path = Path(__file__).resolve().parent
    for parent in [curr] + list(curr.parents):
        if (parent / "package.json").exists() or (parent / "src" / "App.vue").exists():
            return str(parent)
    return None

def get_provider_from_settings(config_dir: str, project_root: Optional[str]) -> Optional[str]:
    """Lee el nombre del proveedor de cable desde settings.json"""
    paths: List[str] = [
        os.path.join(config_dir, "settings.json"),
    ]
    if project_root:
        paths.append(os.path.join(project_root, "config", "settings.json"))

    for path in paths:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data: Any = json.load(f)
                    # Buscar en sección decos/deco o apis
                    provider: Any = (
                        data.get("deco", {}).get("provider") or
                        data.get("decos", [{}])[0].get("provider") if isinstance(data.get("decos"), list) else None or
                        data.get("apis", {}).get("CABLE_PROVIDER")
                    )
                    if provider:
                        return str(provider).lower().strip()
            except Exception:
                pass
    return None

def load_channels(project_root: Optional[str]) -> Dict[str, str]:
    """
    Carga el mapeo de canales con estrategia de búsqueda genérica por glob.
    
    Orden de prioridad:
      1. channels_<proveedor>.json (del proveedor configurado en settings.json)
      2. channels_*.json (cualquier archivo de operadora, encontrado por glob)
      3. channels.json (fallback genérico)
    """
    import glob
    channels: Dict[str, str] = {}
    
    xdg_config: Optional[str] = os.environ.get("XDG_CONFIG_HOME")
    config_dir: str = str(Path(xdg_config) / "Fina") if xdg_config else str(Path.home() / ".config" / "Fina")

    # --- Detectar proveedor desde settings.json ---
    provider: Optional[str] = get_provider_from_settings(config_dir, project_root)

    # --- Construir lista de candidatos ordenada por prioridad ---
    candidates: List[str] = []

    # 1. Archivo específico del proveedor configurado
    if provider:
        named_file: str = f"channels_{provider}.json"
        candidates.append(os.path.join(config_dir, named_file))
        if project_root:
            candidates.append(os.path.join(project_root, "config", named_file))

    # 2. Cualquier channels_*.json encontrado por glob (excluye channels.json genérico)
    glob_pattern_xdg: str = os.path.join(config_dir, "channels_*.json")
    for found in sorted(glob.glob(glob_pattern_xdg)):
        if found not in candidates:
            candidates.append(found)

    if project_root:
        glob_pattern_proj: str = os.path.join(str(project_root), "config", "channels_*.json")
        for found in sorted(glob.glob(glob_pattern_proj)):
            if found not in candidates:
                candidates.append(found)

    # 3. Fallback: channels.json genérico
    candidates.append(os.path.join(config_dir, "channels.json"))
    if project_root:
        candidates.append(os.path.join(str(project_root), "config", "channels.json"))

    # --- Cargar el primero que tenga datos válidos ---
    for path in candidates:
        if not os.path.exists(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and "name" in item and "number" in item:
                            key: str = str(item["name"]).lower().replace(" ", "").strip()
                            channels[key] = str(item["number"])
                elif isinstance(data, dict):
                    for name, number in data.items():
                        key_d: str = str(name).lower().replace(" ", "").strip()
                        channels[key_d] = str(number)
                
                if channels:
                    # Mostrar de qué proveedor/archivo se cargaron
                    fname: str = os.path.basename(path)
                    detected: str = fname.replace("channels_", "").replace(".json", "").capitalize()
                    label: str = f"proveedor '{detected}'" if "_" in fname else "genérico"
                    print(f"📖 Cargados {len(channels)} canales [{label}] desde {path}")
                    return channels
        except Exception as e:
            print(f"⚠️ Error cargando {path}: {e}")
        
    return channels


async def main() -> None:
    """Función principal de sintonización de canales"""
    parser = argparse.ArgumentParser(description="Sintonizar canal en Deco Telecentro")
    parser.add_argument("--ip", required=True, help="IP del Decodificador")
    parser.add_argument("--channel", required=True, help="Nombre o número del canal")
    args = parser.parse_args()

    project_root: Optional[str] = find_project_root()
    channel_to_send: str = str(args.channel)
    
    # Intento de resolución de nombre de canal
    if not any(c.isdigit() for c in channel_to_send):
        channels_map: Dict[str, str] = load_channels(project_root)
        search_key: str = channel_to_send.lower().replace(" ", "").strip()
        if search_key in channels_map:
            channel_to_send = channels_map[search_key]
            print(f"🎯 Mapeado '{args.channel}' -> {channel_to_send}")
        else:
            print(f"❌ No se encontró el canal '{args.channel}' en la configuración.")
    
    print(f"📺 Sintonizando {channel_to_send} en {args.ip}...")
    success: bool = await send_command(args.ip, "channel", channel_to_send)
    if success:
        print("✅ Comando enviado con éxito.")
    else:
        print("❌ Error al enviar el comando al Decodificador.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    except Exception as fatal:
        print(f"✗ Fatal: {fatal}")
        sys.exit(1)
