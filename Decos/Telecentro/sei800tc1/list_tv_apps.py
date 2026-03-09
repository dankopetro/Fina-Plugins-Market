#!/usr/bin/env python3
"""
list_tv_apps.py - Sincronizador automático del catálogo de aplicaciones para Decos Android TV.

Flujo:
  1. Identifica el proveedor (mDNS/Cast)
  2. Escanea aplicaciones instaladas vía ADB (pm list packages)
  3. Si ADB falla, cae a un catálogo cloud curado basado en el proveedor
  4. Guarda/Actualiza la lista de apps en settings.json (XDG_CONFIG_HOME)
"""
import subprocess
import json
import os
import sys
import argparse
import logging
from pathlib import Path
from typing import Optional, Dict, List, Any

# Configuración de logging básica
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger("list_tv_apps")

def find_project_root() -> Optional[str]:
    """Busca la raíz del proyecto basándose en marcadores conocidos"""
    curr: Path = Path(__file__).resolve().parent
    for parent in [curr] + list(curr.parents):
        if (parent / "package.json").exists() or (parent / "src" / "App.vue").exists():
            return str(parent)
    return None

def get_config_dir() -> str:
    """Obtiene el directorio de configuración de Fina siguiendo estándares XDG"""
    xdg_config: Optional[str] = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config:
        return str(Path(xdg_config) / "Fina")
    return str(Path.home() / ".config" / "Fina")

def get_settings_path() -> str:
    """Resuelve la ruta completa a settings.json con fallback al proyecto"""
    config_dir: str = get_config_dir()
    standard_path: str = os.path.join(config_dir, "settings.json")
    
    if os.path.exists(standard_path):
        return standard_path
        
    proj_root: Optional[str] = find_project_root()
    if proj_root:
        fallback_path: str = os.path.join(proj_root, "config", "settings.json")
        if os.path.exists(fallback_path):
            return fallback_path
            
    return standard_path

def identify_provider(ip: str) -> str:
    """Identificación de la identidad del dispositivo vía mDNS/Chromecast"""
    logger.info(f"📡 [0/3] Identificando identidad en {ip}...")
    try:
        # avahi-browse es silenciado un poco más para que no ensucie la salida
        res = subprocess.run(f"avahi-browse -rt _googlecast._tcp 2>/dev/null | grep -i '{ip}' -A 10", 
                           shell=True, capture_output=True, text=True, timeout=5) # type: ignore
        if "fn=" in res.stdout:
            name: str = res.stdout.split("fn=")[1].split("]")[0].replace("[", "").strip()
            logger.info(f"✅ Identidad detectada: '{name}'")
            return name.lower()
    except Exception:
        pass
    return "desconocido"

def get_app_name_heuristic(pkg: str) -> Optional[str]:
    """Heurística para convertir un ID de paquete en un nombre legible para la UI"""
    # Ignorar paquetes de sistema obvios, excepto youtube
    if any(x in pkg for x in ["android.", "google.", "mediatek.", "realtek.", "android.auto"]):
        if "youtube" not in pkg:
            return None
            
    parts = pkg.split('.')
    if len(parts) < 2: return pkg.capitalize()
    
    # Tomar la última parte como nombre
    name = parts[-1].capitalize()
    # Si la última parte es genérica, tomar la penúltima
    if name in ["Android", "Tv", "Launcher", "Main", "Player", "App", "Ninja", "Appbox"]:
        name = parts[-2].capitalize()
        
    # Casos especiales manuales
    mapping = {
        "Ninja": "Netflix",
        "Youtube": "Youtube",
        "Amazonvideo": "Prime Video",
        "Hbonow": "Max (HBO)",
        "Livingroom": "Prime Video",
        "Tplay": "Telecentro Play",
        "Disneyplus": "Disney+",
        "Starplus": "Star+"
    }
    return mapping.get(name, name)

def scan_internal_apps(ip: str) -> Optional[Dict[str, str]]:
    """Escaneo directo de aplicaciones instaladas vía ADB"""
    logger.info(f"🔍 [1/3] Intentando listar aplicaciones instaladas vía ADB...")
    try:
        subprocess.run(["adb", "connect", f"{ip}:5555"], capture_output=True, timeout=3) # type: ignore
        # Listamos solo paquetes de terceros (-3) para reducir ruido
        res = subprocess.run(["adb", "-s", f"{ip}:5555", "shell", "pm", "list", "packages", "-3"], 
                           capture_output=True, text=True, timeout=8) # type: ignore
        
        if res.returncode == 0 and "package:" in res.stdout:
            found_apps: Dict[str, str] = {}
            for line in res.stdout.splitlines():
                if not line.startswith("package:"): continue
                pkg = line.replace('package:', '').strip()
                if not pkg: continue
                
                name = get_app_name_heuristic(pkg)
                if name:
                    found_apps[name] = pkg
            
            if found_apps:
                logger.info(f"✅ Extraídas {len(found_apps)} aplicaciones directamente del Deco.")
                return found_apps
    except Exception as e:
        logger.debug(f"ADB no accesible: {e}")
    
    logger.warning("⚠️ ADB no pudo extraer la lista de aplicaciones.")
    return None

def fetch_cloud_apps(provider_name: str) -> Dict[str, str]:
    """Asignación de catálogo de apps inteligente basado en la operadora/proveedor"""
    logger.info(f"☁️ [2/3] Buscando catálogo curado en la nube...")
    
    # Base de datos estática curada para casos sin ADB
    cloud_db: Dict[str, Dict[str, str]] = {
        "telecentro": {
            "Youtube": "com.google.android.youtube.tv",
            "Netflix": "com.netflix.ninja",
            "Prime Video": "com.amazon.amazonvideo.livingroom",
            "Disney+": "com.disney.disneyplus",
            "HBO Max": "com.hbo.hbonow",
            "Telecentro Play": "com.telecentro.tplay.app",
            "Spotify": "com.spotify.tv.android",
            "Paramount+": "com.viacom.paramountplus"
        },
        "flow": {
            "Flow": "com.cablevision.flow",
            "Youtube": "com.google.android.youtube.tv",
            "Netflix": "com.netflix.ninja",
            "Prime Video": "com.amazon.amazonvideo.livingroom"
        },
        "default": {
            "Youtube": "com.google.android.youtube.tv",
            "Netflix": "com.netflix.ninja",
            "Prime Video": "com.amazon.amazonvideo.livingroom"
        }
    }
    
    # Búsqueda suave del proveedor
    for key in cloud_db:
        if key in provider_name.lower():
            logger.info(f"✅ Se cargó el catálogo de aplicaciones para: {key.capitalize()}")
            return cloud_db[key]
            
    return cloud_db["default"]

def update_fina_settings(found_apps: Dict[str, str]) -> None:
    """Guarda o actualiza las aplicaciones en settings.json del usuario"""
    settings_file = get_settings_path()
    logger.info(f"💾 Guardando sincronización en {settings_file}...")
    
    os.makedirs(os.path.dirname(settings_file), exist_ok=True)
    
    data: Dict[str, Any] = {}
    if os.path.exists(settings_file):
        try:
            with open(settings_file, 'r', encoding='utf-8') as f:
                content = f.read()
                if content.strip():
                   loaded = json.loads(content)
                   if isinstance(loaded, dict):
                       data.update(loaded)
        except Exception as e:
            logger.error(f"⚠️ Error leyendo settings actual: {e}")

    # Obtener y verificar sección de apps de forma segura para el linter
    tv_apps: Any = data.get("tv_apps")
    if not isinstance(tv_apps, dict):
        tv_apps = {}
        data["tv_apps"] = tv_apps
        
    tv_apps.update(found_apps)
    
    try:
        with open(settings_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        logger.info(f"✅ Sincronización finalizada. {len(found_apps)} aplicaciones registradas.")
    except Exception as e:
        logger.error(f"❌ Error al escribir en settings.json: {e}")

def main() -> None:
    parser = argparse.ArgumentParser(description="Sincronizador Automático de Catálogo de Apps Android TV")
    parser.add_argument("--ip", required=True, help="IP del dispositivo (Deco/TV)")
    args = parser.parse_args()

    # Paso 0: Identificar identidad mDNS
    provider: str = identify_provider(args.ip)
    
    # Paso 1: Escaneo real vía ADB
    apps_from_adb = scan_internal_apps(args.ip)
    
    # Paso 2: Catálogo inteligente (fallback o complemento)
    apps: Dict[str, str] = apps_from_adb if apps_from_adb else fetch_cloud_apps(provider)

    if apps:
        logger.info(f"\n✨ Sincronización completada para {provider.upper()}")
        for name, pkg in apps.items():
             logger.info(f"  📺 {name: <15} -> {pkg}")
             
        # Guardar resultados para que Fina las use
        update_fina_settings(apps)
    else:
        logger.error("\n❌ No fue posible sincronizar el catálogo de aplicaciones.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("\n⏹ Sincronización interrumpida por el usuario.")
    except Exception as e:
        logger.error(f"✗ Fatal: {e}")
        sys.exit(1)
