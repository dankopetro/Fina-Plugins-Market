#!/usr/bin/env python3
"""
scan_ultra_fast.py - Fina Market Plugin (TCL 32S60A)
=====================================================
Detección inteligente de tipo de señal y escaneo de canales.

ESTRATEGIA UNIVERSAL:
  1. Intenta leer canales desde la base de datos interna de la TV (Android TV content provider)
  2. Si no hay datos disponibles, detecta el tipo de señal activa (Antena o Cable)
  3. Basado en el tipo, escanea el rango correcto:
     - Antena / ISDB-T   → 2.1 al 13.3
     - Cable / Analógico → 1 al 125 (estilo Argentina: 80.x a 89.x para Telecentro)
  4. Todos los canales encontrados se guardan; el usuario desactiva los que no recibe desde Fina.

IMPORTANTE PARA DEVELOPERS:
  Si el proveedor de contenido (content://android.media.tv/channel) está disponible
  en el dispositivo target, ES LA FUENTE MÁS CONFIABLE. En TCL sin root no está expuesto.
  Para otros fabricantes (Sony, Sharp, Sharp) puede sí estar disponible.
"""

import subprocess
import json
import time
import os
import re
import argparse
import urllib.request
import urllib.parse
from pathlib import Path
from typing import Optional, Dict, List, Any, Tuple

CANCEL_FILE: str = "/tmp/fina_cancel_scan"

# --- Helpers de portabilidad ---
def find_project_root() -> Optional[str]:
    curr: Path = Path(__file__).resolve().parent
    for parent in [curr] + list(curr.parents):
        if (parent / "package.json").exists() or (parent / "src" / "App.vue").exists():
            return str(parent)
    return None

def get_config_dir() -> str:
    xdg: Optional[str] = os.environ.get("XDG_CONFIG_HOME")
    return str(Path(xdg) / "Fina") if xdg else str(Path.home() / ".config" / "Fina")

def _slug_from_device_name(name: str) -> str:
    providers: Dict[str, List[str]] = {
        "telecentro": ["telecentro", "sei800", "tc-"],
        "flow":       ["flow", "cablevision", "cv-"],
        "directv":    ["directv", "dtv", "sky"],
        "claro":      ["claro", "cvc"],
        "personal":   ["personal", "ar-telecom"],
    }
    for slug, keywords in providers.items():
        if any(kw in name for kw in keywords):
            return slug
    return "desconocido"

def identify_cable_provider(ip: str) -> str:
    """Detecta el proveedor de cable vía mDNS o ADB"""
    try:
        res = subprocess.run(
            f"avahi-browse -rt _googlecast._tcp 2>/dev/null | grep -i '{ip}' -A 15",
            shell=True, capture_output=True, text=True, timeout=5
        ) # type: ignore
        if "fn=" in res.stdout:
            name: str = res.stdout.split("fn=")[1].split("]")[0].replace("[", "").strip().lower()
            return _slug_from_device_name(name)
    except Exception:
        pass
    return "desconocido"

# ---------------------------------------------------------------------------
def search_guide_urls(provider: str) -> Dict[str, Any]:
    """
    Meta-Buscador Universal — usa DuckDuckGo Lite y Brave Search.
    Busca la guía de canales más reciente y ordena por relevancia.
    """
    found_urls: List[Tuple[str, int]] = []
    unique_links: set[str] = set()

    import datetime
    current_year = datetime.date.today().year
    
    queries = [
        f"guia de canales {provider}",
        f"guide channels {provider}",
        f"channel lineup {provider}",
        f"grilla {provider}",
        f"site:foromedios.com {provider} grilla"
    ]

    for query in queries:
        urls_batch = []
        try:
            req = urllib.request.Request(
                "https://lite.duckduckgo.com/lite/",
                data=urllib.parse.urlencode({'q': query}).encode('utf-8'),
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; rv:109.0) Gecko/20100101 Firefox/115.0",
                    "Content-Type": "application/x-www-form-urlencoded"
                }
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
            links = re.findall(r'href="(https?://[^"& ]+)"', html)
            urls_batch.extend([l for l in links if "duckduckgo" not in l])
        except: pass

        if not urls_batch:
            try:
                brave_url = f"https://search.brave.com/search?q={urllib.parse.quote(query)}&source=web"
                req = urllib.request.Request(brave_url, headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept": "text/html",
                })
                with urllib.request.urlopen(req, timeout=8) as resp:
                    html = resp.read().decode("utf-8", errors="ignore")
                urls_batch.extend(re.findall(r'href="(https?://[^"& ]+)"', html))
            except: pass

        for l in urls_batch:
            u = str(urllib.parse.unquote(l))
            u_low = u.lower()
            if any(x in u_low for x in ["duckduckgo", "brave.com", "facebook", "youtube", "twitter", "instagram", "wikipedia"]): continue
            
            score = 0
            if str(current_year + 1) in u_low: score += 30
            elif str(current_year) in u_low: score += 20
            elif str(current_year - 1) in u_low: score += 5

            if "foromedios" in u_low or "forounivers" in u_low: score += 25
            if "scribd" in u_low or "pastebin" in u_low or "selectra" in u_low: score += 10
            
            if provider.lower() + ".com.ar" in u_low or provider.lower() + ".com/" in u_low:
                score += 15

            if provider.lower() in u_low or "grilla" in u_low or "canales" in u_low:
                if u not in unique_links:
                    unique_links.add(u)
                    found_urls.append((u, score))

    if not found_urls:
        for ext in ["com.ar", "com", "net"]:
            for path in ["/canales", "/grilla", ""]:
                found_urls.append((f"https://www.{provider}.{ext}{path}", 0))
    else:
        roots: List[str] = [f"www.{provider}.com.ar", f"www.{provider}.com"]
        for u_item, _ in found_urls:
            if "//" in u_item:
                parts = u_item.split("/")
                if len(parts) > 2: roots.append(parts[2])
        for root in list(set(roots)):
            for path in ["/canales", "/grilla", "/json/mockup/apiChannels.json", "/api/channels", "/api/canales", "/channels.json"]:
                cand = f"https://{root}{path}"
                if cand not in unique_links:
                    unique_links.add(cand)
                    bonus = 150
                    if provider.lower() in cand: bonus += 150
                    if ".json" not in cand and "/api/" not in cand: bonus = 5
                    found_urls.append((cand, bonus))

    found_urls.sort(key=lambda x: x[1], reverse=True)
    unique_final = []
    seen = set()
    for u, _ in found_urls:
        if u not in seen:
            unique_final.append(u); seen.add(u)
            
    return {"urls": unique_final, "snippets": {}}


def fetch_cloud_list(provider: str, project_root: Optional[str]) -> Optional[List[Dict[str, str]]]:
    """Descarga lista curada desde el repositorio de Fina en GitHub"""
    filename: str = f"channels_{provider}.json"
    url: str = f"https://raw.githubusercontent.com/dankopetro/Fina-Plugins-Market/main/channels/{filename}"
    try:
        with urllib.request.urlopen(url, timeout=6) as resp:
            data_raw: Any = json.loads(resp.read().decode())
            if data_raw:
                print(f"☁️ Lista '{provider}' descargada desde Fina Market.")
                return _normalize_channels(data_raw)
    except Exception:
        pass
    if project_root:
        local_p: str = os.path.join(str(project_root), "config", filename)
        if os.path.exists(local_p):
            try:
                with open(local_p, "r", encoding="utf-8") as f:
                    return _normalize_channels(json.load(f))
            except Exception:
                pass
    return None

JS_TRASH = ["index", "math", "null", "true", "false", "function", "sqrt", "switch", "case", "undefined"]

def fetch_from_web(provider: str) -> Optional[List[Dict[str, str]]]:
    """Web scraping dinámico con soporte nativo para JSON y SPAs"""
    discovery = search_guide_urls(provider)
    urls = discovery.get("urls", [])
    if not urls: return None

    print(f"🕵️‍♂️ [Hiper-Buscador] Procesando {len(urls)} fuentes potenciales...")
    best_channels: List[Dict[str, str]] = []

    for url in urls[:15]:
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html,application/json;q=0.9,*/*;q=0.8"
            })
            with urllib.request.urlopen(req, timeout=10) as resp:
                content_type = resp.headers.get("Content-Type", "")
                html = resp.read().decode("utf-8", errors="ignore")

            channels = []
            # 1. JSON NATIVO
            if "json" in content_type or url.endswith(".json") or ("{" in html[:50] and "}" in html[-50:]):
                try:
                    data = json.loads(html)
                    items = data if isinstance(data, list) else data.get("data", data.get("channels", []))
                    if isinstance(items, dict): items = list(items.values())
                    for item in items:
                        if not isinstance(item, dict): continue
                        num = item.get("channel") or item.get("n") or item.get("number") or item.get("id")
                        name = item.get("name") or item.get("c") or item.get("title") or item.get("nombre")
                        if num is not None and name:
                            ch_n = str(num).strip()
                            if ch_n.isdigit() and 0 < int(ch_n) < 2000:
                                channels.append({"n": ch_n, "c": str(name).strip()})
                    if len(channels) > 40: return channels
                except: pass

            # 2. HTML -> TEXT
            if len(html) > 1000:
                clean = re.sub(r'<(script|style|nav|footer|head)[^>]*>.*?</\1>', ' ', html, flags=re.DOTALL | re.IGNORECASE)
                text = re.sub(r'<[^>]+>', '\n', clean)
                lines = [l.strip() for l in text.splitlines() if len(l.strip()) > 1]
                for line in lines:
                    m1 = re.match(r'^(\d{1,4})\s+([A-Za-z][A-Za-z0-9\s\.&+-]{2,28})$', line)
                    m2 = re.match(r'^([A-Za-z][A-Za-z0-9\s\.&+-]{2,28})\s+(\d{1,4})$', line)
                    m = m1 or m2
                    if m:
                        n, c = (m.group(1), m.group(2)) if m1 else (m.group(2), m.group(1))
                        if 0 < int(n) < 2000 and not any(bad in c.lower() for bad in JS_TRASH):
                            channels.append({"n": str(int(n)), "c": c.strip()})
                
                if len(channels) > len(best_channels): best_channels = list(channels)
                if len(channels) > 100: return channels
        except: continue

    return best_channels if len(best_channels) > 10 else None

def _normalize_channels(data: Any) -> List[Dict[str, str]]:
    """Normaliza lista o dict de canales al formato Fina Standard: [{n, c}]"""
    out: List[Dict[str, str]] = []
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                n = str(item.get("n", item.get("num", item.get("number", ""))))
                c = str(item.get("c", item.get("name", "")))
                if n and c: out.append({"n": n, "c": c})
    elif isinstance(data, dict):
        for name, number in data.items():
            out.append({"n": str(number), "c": str(name)})
    return out

def save_channels(channels: List[Dict[str, str]], provider: str, config_dir: str) -> str:
    """Guarda como channels_<proveedor>.json en formato Fina Estándar"""
    os.makedirs(config_dir, exist_ok=True)
    slug: str = provider if provider != "desconocido" else "generic"
    path: str = os.path.join(config_dir, f"channels_{slug}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(channels, f, indent=4, ensure_ascii=False)
    print(f"✅ {len(channels)} canales guardados en {path}")
    return slug

def update_settings_provider(provider_slug: str, config_dir: str, project_root: Optional[str]) -> None:
    """Escribe el proveedor detectado en settings.json automáticamente"""
    settings_path: str = os.path.join(config_dir, "settings.json")
    if not os.path.exists(settings_path) and project_root:
        alt: str = os.path.join(str(project_root), "config", "settings.json")
        if os.path.exists(alt):
            settings_path = alt
    # Cargar datos existentes o iniciar con dict vacío
    data: Dict[str, Any] = {}
    if os.path.exists(settings_path):
        try:
            with open(settings_path, "r", encoding="utf-8") as f:
                loaded: Any = json.load(f)
                if isinstance(loaded, dict):
                    data.update(loaded)
        except Exception:
            pass

    # Reconstrucción de datos para satisfacer al linter (evita uniones de tipos)
    new_data: Dict[str, Any] = {str(k): v for k, v in data.items()}
    
    current_apis = new_data.get("apis", {})
    if not isinstance(current_apis, dict):
        current_apis = {}
    
    # Actualización segura: sección apis limpia
    apis_update: Dict[str, Any] = {str(k): v for k, v in current_apis.items()}
    apis_update["CABLE_PROVIDER"] = provider_slug
    new_data["apis"] = apis_update

    try:
        os.makedirs(os.path.dirname(settings_path), exist_ok=True)
        with open(settings_path, "w", encoding="utf-8") as f:
            json.dump(new_data, f, indent=4, ensure_ascii=False)
        print(f"📝 Proveedor '{provider_slug}' registrado con éxito en settings.json")
    except Exception as e:
        print(f"⚠️ No se pudo actualizar settings.json: {e}")


# Keycodes ADB para dígitos
KEY_MAP: Dict[str, str] = {
    '0': '7', '1': '8', '2': '9', '3': '10', '4': '11',
    '5': '12', '6': '13', '7': '14', '8': '15', '9': '16',
    '.': '158'
}

def check_cancel() -> bool:
    if os.path.exists(CANCEL_FILE):
        print("\n🛑 CANCELACIÓN DETECTADA")
        try:
            os.remove(CANCEL_FILE)
        except Exception:
            pass
        return True
    return False

def adb(ip: str, *args: str, timeout: int = 5) -> str:
    try:
        cmd = ['adb', '-s', f'{ip}:5555', 'shell'] + list(args)
        result = subprocess.run(
            cmd,
            capture_output=True, text=True, timeout=timeout
        ) # type: ignore
        return result.stdout.strip()
    except Exception:
        return ""

def try_read_tv_database(ip: str) -> Optional[Dict[str, str]]:
    """
    Intenta leer canales de la base de datos interna de AndroidTV.
    """
    print("🔍 Intentando leer base de datos interna de la TV...")
    raw = adb(ip, 'content', 'query', '--uri', 'content://android.media.tv/channel',
              '--projection', 'display_name:channel_number', timeout=6)
    
    if not raw or "No result found" in raw or "Error" in raw:
        print("⚠️  Base de datos interna no accesible (normal en TCL/sin root)")
        return None

    channels: Dict[str, str] = {}
    for line in raw.splitlines():
        name_match = re.search(r'display_name=([^,]+)', line)
        num_match  = re.search(r'channel_number=([^,\s]+)', line)
        if name_match and num_match:
            name = name_match.group(1).strip()
            num  = num_match.group(1).strip()
            if name and num:
                channels[name] = num
    
    if channels:
        print(f"✅ {len(channels)} canales leídos de la TV directamente!")
        return channels
    return None

def detect_signal_type(ip: str) -> str:
    """
    Detecta qué tipo de señal está usando la TV ahora mismo.
    """
    print("🔍 Detectando tipo de señal...")
    
    # Revisar el input source activo
    input_info = adb(ip, 'dumpsys', 'activity', 'top', timeout=3)
    
    # Buscar si la actividad actual es la app de TV nativa
    if 'TVActivity' in input_info or 'tv.TVActivity' in input_info:
        # Leer URI actual para saber si es antenna o cable
        uri_info = adb(ip, 'dumpsys', 'window', 'windows', timeout=3)
        if 'channel/0' in uri_info or 'antenna' in uri_info.lower():
            return 'antenna'
        return 'cable'

    return 'unknown'

def build_channel_list(signal_type: str, cable_range: Tuple[int, int] = (80, 89)) -> Dict[str, str]:
    """
    Genera lista de canales según el tipo de señal detectado.
    """
    channels: Dict[str, str] = {}
    
    if signal_type == 'antenna':
        print("📡 Señal detectada: ANTENA (ISDB-T) → Canales 2.1 al 13.3")
        for main in range(2, 14):
            for sub in range(1, 4):
                key = f"{main}.{sub}"
                channels[f"Canal {key}"] = key
    
    elif signal_type == 'cable':
        print(f"📡 Señal detectada: CABLE → Canales {cable_range[0]}.1 al {cable_range[1]}.9")
        for main in range(cable_range[0], cable_range[1] + 1):
            for sub in range(1, 10):
                key = f"{main}.{sub}"
                channels[f"Canal {key}"] = key
    
    else:
        # Desconocido: escanear ambos rangos
        print("📡 Señal desconocida → Escaneando antena (2.1-13.3) + cable (80.1-89.9)")
        for main in range(2, 14):
            for sub in range(1, 4):
                key = f"{main}.{sub}"
                channels[f"Canal {key}"] = key
        for main in range(80, 90):
            for sub in range(1, 10):
                key = f"{main}.{sub}"
                channels[f"Canal {key}"] = key
    
    return channels

def go_to_tv_input(ip: str) -> bool:
    """Ir a TV/Aire antes de enviar los keycodes de canal."""
    try:
        subprocess.run(
            ['adb', '-s', f'{ip}:5555', 'shell', 'am', 'start', '-a',
             'android.intent.action.VIEW', '-d', 'content://android.media.tv/channel/0',
             '-n', 'com.tcl.tv/.TVActivity'],
            capture_output=True, timeout=5
        ) # type: ignore
        time.sleep(1.5)
        return True
    except Exception as e:
        print(f"❌ Error activando TV/Aire: {e}")
        return False

def send_channel_keys(ip: str, channel_str: str) -> bool:
    # Aseguramos que solo pasamos strings no nulas
    keycodes: List[str] = [KEY_MAP[c] for c in channel_str if c in KEY_MAP]
    if not keycodes:
        return False
    try:
        subprocess.run(
            ['adb', '-s', f'{ip}:5555', 'shell', 'input', 'keyevent'] + keycodes,
            capture_output=True, timeout=2
        ) # type: ignore
        time.sleep(0.15)
        subprocess.run(
            ['adb', '-s', f'{ip}:5555', 'shell', 'input', 'keyevent', '66'],
            capture_output=True, timeout=2
        ) # type: ignore
        time.sleep(0.8)
        return True
    except Exception:
        return False

def main() -> None:
    parser = argparse.ArgumentParser(description="Fina Smart Channel Scanner")
    parser.add_argument("--ip", required=True, help="IP de la TV")
    parser.add_argument("--force-type", choices=["antenna", "cable", "both"],
                        help="Forzar tipo de señal (antenna/cable/both) sin auto-detección")
    parser.add_argument("--cable-from", type=int, default=80, help="Canal cable desde (default: 80)")
    parser.add_argument("--cable-to",   type=int, default=89, help="Canal cable hasta (default: 89)")
    args = parser.parse_args()

    target_ip: str = str(args.ip)
    project_root: Optional[str] = find_project_root()
    config_dir: str = get_config_dir()

    if os.path.exists(CANCEL_FILE):
        os.remove(CANCEL_FILE)

    print("⚡ Fina Smart Channel Scanner")
    print(f"📡 TV: {target_ip}")
    print()

    # ESTRATEGIA 0: Identificar proveedor de cable
    provider: str = identify_cable_provider(target_ip)

    # ESTRATEGIA 1: Leer base de datos interna de la TV
    db_channels = try_read_tv_database(target_ip)
    channels_list: List[Dict[str, str]] = []

    if db_channels:
        channels_list = _normalize_channels(db_channels)
        print(f"🏆 Usando datos de la TV directamente: {len(channels_list)} canales")
    else:
        # ESTRATEGIA 1.5: Cloud / Web scraping del proveedor
        if provider != "desconocido":
            cloud = fetch_cloud_list(provider, project_root)
            if not cloud:
                cloud = fetch_from_web(provider)
            if cloud:
                channels_list = cloud
                print(f"🏆 Lista de '{provider}' obtenida automáticamente: {len(channels_list)} canales")

    if not channels_list:
        # ESTRATEGIA 2: Detección de señal + generación de lista + escaneo ADB
        if args.force_type:
            signal = args.force_type if args.force_type != 'both' else 'unknown'
            print(f"⚙️  Tipo forzado por argumento: {args.force_type}")
        else:
            signal = detect_signal_type(target_ip)

        signal_channels = build_channel_list(signal, cable_range=(args.cable_from, args.cable_to))
        channels_list = _normalize_channels(signal_channels)
        print(f"📋 Lista generada: {len(channels_list)} canales para escanear")
        print()

        if not go_to_tv_input(target_ip):
            print("❌ No se pudo acceder a TV/Aire")
            return

        if channels_list:
            for item in channels_list:
                if check_cancel(): break
                num = item.get("n", "")
                print(f"📺 {num}...", end=" ", flush=True)
                send_channel_keys(target_ip, num)
                print("✅")

        print(f"\n📊 Completado: {len(channels_list)} canales procesados")

    # Guardar resultado + registrar proveedor
    if channels_list:
        saved_slug: str = save_channels(channels_list, provider, config_dir)
        update_settings_provider(saved_slug, config_dir, project_root)
    else:
        print("❌ No se obtuvieron canales.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⏹ Escaneo cancelado.")
    except Exception as fatal:
        print(f"✗ Fatal: {fatal}")
        import sys
        sys.exit(1)
