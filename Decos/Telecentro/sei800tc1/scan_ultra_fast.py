#!/usr/bin/env python3
"""
scan_ultra_fast.py — Descubrimiento automático de canales para Deco Android TV.

Flujo completo sin intervención del usuario:
  1. Detecta el proveedor del deco (mDNS/Chromecast identity)
  2. Lee la base de datos interna del Android TV (TIF)
  3. Si falla, busca en el repositorio de Fina (cloud)
  4. Si falla, hace web scraping en el sitio del proveedor
  5. Guarda como channels_<proveedor>.json en ~/.config/Fina/
  6. Escribe el proveedor detectado en settings.json automáticamente
"""
import subprocess
import json
import os
import sys
import re
import argparse
import urllib.request
import urllib.parse
from pathlib import Path
from typing import Optional, Dict, List, Any, Tuple

# --- Detección dinámica de raíz de proyecto ---
def find_project_root() -> Optional[str]:
    """Busca la raíz del proyecto basándose en marcadores conocidos"""
    curr: Path = Path(__file__).resolve().parent
    for parent in [curr] + list(curr.parents):
        if (parent / "package.json").exists() or (parent / "src" / "App.vue").exists():
            return str(parent)
    return None

def get_config_dir() -> str:
    """Directorio de configuración de Fina (estándar XDG)"""
    xdg: Optional[str] = os.environ.get("XDG_CONFIG_HOME")
    return str(Path(xdg) / "Fina") if xdg else str(Path.home() / ".config" / "Fina")

# ---------------------------------------------------------------------------
# PASO 0: Detectar el proveedor del deco
# ---------------------------------------------------------------------------
def identify_provider(ip: str) -> str:
    """
    Identifica el proveedor de cable leyendo el nombre del dispositivo
    Chromecast vía mDNS (avahi-browse). Pasos:
      1. Chromecast friendly name (fn=)
      2. Nombre del modelo ADB
    """
    print(f"📡 [0/3] Identificando proveedor en {ip}...")

    # Intento 1: mDNS Chromecast
    try:
        res = subprocess.run(
            f"avahi-browse -rt _googlecast._tcp 2>/dev/null | grep -i '{ip}' -A 15",
            shell=True, capture_output=True, text=True, timeout=5
        ) # type: ignore
        if "fn=" in res.stdout:
            name: str = res.stdout.split("fn=")[1].split("]")[0].replace("[", "").strip().lower()
            print(f"✅ Identidad Chromecast: '{name}'")
            # Mapear al slug del proveedor
            return _slug_from_device_name(name)
    except Exception:
        pass

    # Intento 2: nombre del modelo ADB
    try:
        res2 = subprocess.run(
            ["adb", "-s", f"{ip}:5555", "shell", "getprop", "ro.product.model"],
            capture_output=True, text=True, timeout=3
        ) # type: ignore
        model: str = res2.stdout.strip().lower()
        if model:
            print(f"ℹ️ Modelo ADB: '{model}'")
            return _slug_from_device_name(model)
    except Exception:
        pass

    return "desconocido"

def _slug_from_device_name(name: str) -> str:
    """Extrae el slug del proveedor de forma agnóstica"""
    # Limpieza básica para obtener un slug puro
    slug = re.sub(r'[^a-z0-9]', '', name.lower())
    # Si el nombre contiene palabras clave de marcas globales, las normalizamos
    globals_map = {"directv": "directv", "movistar": "movistar", "claro": "claro", "orange": "orange", "vodafone": "vodafone"}
    for k, v in globals_map.items():
        if k in slug: return v
    return slug if len(slug) > 2 else "desconocido"

# ---------------------------------------------------------------------------
# PASO 1: Base de datos interna Android TV (TIF)
# ---------------------------------------------------------------------------
def scan_internal_db(ip: str) -> Optional[List[Dict[str, str]]]:
    """Interroga la base de datos TIF nativa de Android TV"""
    print("🔍 [1/3] Leyendo base de datos interna de Android TV...")
    try:
        subprocess.run(["adb", "connect", f"{ip}:5555"], capture_output=True, timeout=2) # type: ignore
        res = subprocess.run(
            ["adb", "-s", f"{ip}:5555", "shell", "content", "query",
             "--uri", "content://android.media.tv/channel",
             "--projection", "display_name:display_number"],
            capture_output=True, text=True, timeout=8
        ) # type: ignore
        if res.returncode == 0 and "display_name=" in res.stdout:
            channels: List[Dict[str, str]] = []
            for line in res.stdout.splitlines():
                if "display_name=" in line:
                    parts: List[str] = line.split("display_name=")
                    name: str = parts[1].split(",")[0].strip()
                    num_parts: List[str] = line.split("display_number=")
                    num: str = num_parts[1].strip() if len(num_parts) > 1 else ""
                    if name and num:
                        channels.append({"n": num, "c": name, "s": "General"})
            if channels:
                print(f"✅ {len(channels)} canales leídos desde la DB interna.")
                return channels
    except Exception as e:
        print(f"ℹ️ DB interna no disponible: {e}")
    return None

# ---------------------------------------------------------------------------
# PASO 2.5: Descubrimiento Dinámico (Hiper-Buscador)
# ---------------------------------------------------------------------------
def search_guide_urls(provider: str) -> Dict[str, Any]:
    """
    Meta-Buscador Universal — usa Brave Search (funciona sin bloqueo).
    Busca la guia de canales más reciente, ordena por fecha y devuelve URLs.
    """
    found_urls: List[Tuple[str, int]] = []
    unique_links: set[str] = set()

    # Obtener el año actual dinámicamente para el scoring
    import datetime
    current_year = datetime.date.today().year
    
    # Queries ordenadas por precisión y madurez del término:
    # 1. "guia de canales" (más usado modernamente)
    # 2. "guide channels" / "channel lineup"
    # 3. "grilla" (término clásico de foros)
    queries = [
        f"guia de canales {provider}",
        f"guide channels {provider}",
        f"channel lineup {provider}",
        f"grilla {provider}",
        f"site:foromedios.com {provider} grilla"
    ]

    for query in queries:
        urls_batch = []
        # --- Motor 1: DuckDuckGo Lite (anti-bloqueo total) ---
        try:
            req = urllib.request.Request(
                "https://lite.duckduckgo.com/lite/",
                data=urllib.parse.urlencode({'q': query}).encode('utf-8'),
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; rv:109.0) Gecko/20100101 Firefox/115.0",
                    "Content-Type": "application/x-www-form-urlencoded"
                }
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
            
            links = re.findall(r'href="(https?://[^"& ]+)"', html)
            urls_batch.extend([l for l in links if "duckduckgo" not in l])
        except: pass

        # --- Motor 2: Brave Search (fallback) ---
        if not urls_batch:
            try:
                brave_url = f"https://search.brave.com/search?q={urllib.parse.quote(query)}&source=web"
                req = urllib.request.Request(brave_url, headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept": "text/html",
                    "Accept-Language": "es-AR,es;q=0.9",
                })
                with urllib.request.urlopen(req, timeout=10) as resp:
                    html = resp.read().decode("utf-8", errors="ignore")
                urls_batch.extend(re.findall(r'href="(https?://[^"& ]+)"', html))
            except: pass

        # Procesar lote de enlaces encontrados
        for l in urls_batch:
            u = str(urllib.parse.unquote(l))
            u_low = u.lower()
            # Ignorar basuras de búsqueda
            if any(x in u_low for x in ["duckduckgo", "brave.com", "facebook", "youtube", "twitter", "instagram", "wikipedia"]): continue
            
            # Score de relevancia (Filtro Anti-SPA y prioridad de frescura)
            score = 0
            
            # Acomodar por fecha más reciente dinámicamente
            if str(current_year + 1) in u_low: score += 30 # Próximo año (ej. pre-anuncios)
            elif str(current_year) in u_low: score += 20   # Año en curso
            elif str(current_year - 1) in u_low: score += 5

            
            # Foros y comunidades tienen texto real → bonus alto
            if "foromedios" in u_low or "forounivers" in u_low: score += 25
            if "scribd" in u_low or "pastebin" in u_low or "selectra" in u_low: score += 10
            if "grilla" in u_low or "canales" in u_low or "lineup" in u_low: score += 5
            
            # El sitio oficial del proveedor es fundamental y no se penaliza artificialmente.
            # Si es SPA, la validación de texto más adelante (html2text) extraerá 0 canales 
            # y el script automáticamente pasará al resultado siguiente.
            if provider.lower() + ".com.ar" in u_low or provider.lower() + ".com/" in u_low:
                score += 15 # Bonus por ser el sitio oficial
            
            # Solo URLs relevantes
            if provider.lower() in u_low or "grilla" in u_low or "canales" in u_low or "guia" in u_low:
                if u not in unique_links:
                    unique_links.add(u)
                    found_urls.append((u, score))

    # Fallback: rutas directas inferidas si la búsqueda no encontró nada
    if not found_urls:
        for ext in ["com.ar", "com", "net", "tv"]:
            for path in ["/canales", "/guia-de-canales", "/grilla", ""]:
                found_urls.append((f"https://www.{provider}.{ext}{path}", 0))
    else:
        # Agregar sub-rutas de los dominios encontrados para máxima cobertura
        roots: List[str] = [f"www.{provider}.com.ar", f"www.{provider}.com"]
        for u_item, _ in found_urls:
            if "//" in u_item:
                parts = u_item.split("/")
                if len(parts) > 2: roots.append(parts[2])
        for root in list(set(roots)):
            for path in ["/canales", "/guia-de-canales", "/grilla", "/json/mockup/apiChannels.json", "/api/channels", "/api/canales", "/channels.json"]:
                cand = f"https://{root}{path}"
                if cand not in unique_links:
                    unique_links.add(cand)
                    # A los .json oficiales les damos prioridad MÁXIMA ABSOLUTA (300) por si es el API oficial del SPA
                    bonus = 150
                    if provider.lower() in cand: bonus += 150
                    if ".json" not in cand and "/api/" not in cand: bonus = 5
                    
                    found_urls.append((cand, bonus))

    # Ordenar y deduplicar — las más recientes primero
    found_urls.sort(key=lambda x: x[1], reverse=True)
    unique_final: List[str] = []
    seen: set[str] = set()
    for u, _ in found_urls:
        if u not in seen:
            unique_final.append(u); seen.add(u)
            
    return {"urls": unique_final, "snippets": {}}

JS_TRASH = ["index", "math", "null", "true", "false", "function", "sqrt", "switch", "case", "undefined"]

def fetch_from_web(provider: str) -> Optional[List[Dict[str, str]]]:
    """
    1. DuckDuckGo / Brave Search → busca y ordena por fecha
    2. Toma el resultado más reciente del proveedor (web oficial o foros)
    3. html2text → extrae canales → JSON
    """
    discovery = search_guide_urls(provider)
    urls = discovery.get("urls", [])  # Ya vienen ordenados: más reciente primero
    
    if not urls:
        print("❌ El Hiper-Buscador no devolvió resultados.")
        return None

    print(f"🕵️‍♂️ [Hiper-Buscador] Encontrados {len(urls)} resultados.")
    print(f"🎯 Procesando el más reciente: {urls[0]}\n")

    # Procesar en orden: probar hasta 25 para evitar quedarse en foros vacíos (que usan imagen instead of text)
    best_channels: List[Dict[str, str]] = []

    for url in urls[:25]:  
        print(f"📖 Extrayendo texto de: {url[:75]}")
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
                "Accept-Language": "es-AR,es;q=0.9"
            })
            with urllib.request.urlopen(req, timeout=12) as resp:
                content_type = resp.headers.get("Content-Type", "")
                html = resp.read().decode("utf-8", errors="ignore")

            channels: List[Dict[str, str]] = []

            # ----------------------------------------------------
            # 1. PARSEO NATIVO DE JSON (Para Web Oficiales / SPA)
            # ----------------------------------------------------
            is_json_request = "application/json" in content_type or url.endswith(".json") or ("{" in html[:50] and "}" in html[-50:])
            if is_json_request:
                try:
                    data = json.loads(html)
                    # Aplanar cualquier JSON para buscar listas
                    items = data if isinstance(data, list) else data.get("data", data.get("channels", []))
                    if isinstance(items, dict): items = list(items.values())

                    for item in items:
                        if not isinstance(item, dict): continue
                        
                        # Buscar keys clásicas de APIs
                        num = item.get("channel") or item.get("n") or item.get("number") or item.get("id")
                        name = item.get("name") or item.get("c") or item.get("title") or item.get("nombre")
                        cat = item.get("packDescription") or item.get("category") or item.get("s") or "General"
                        
                        if num is not None and name:
                            ch_n = str(num).strip()
                            if ch_n.isdigit() and int(ch_n) > 0 and int(ch_n) < 2000:
                                channels.append({"n": ch_n, "c": str(name).strip()})
                    
                    if len(channels) > 40:
                        print(f"🏆 VICTORIA ÉPICA: {len(channels)} canales extraídos nativamente de API JSON oficial.")
                        return channels
                except: pass
                if not channels:
                    print(f"   ↳ Es JSON pero no se encontraron canales, saltando...")
                    continue


            # ----------------------------------------------------
            # 2. PARSEO HTML -> TEXT (Para Foros y Webs comunes)
            # ----------------------------------------------------
            if len(html) < 1000:
                print(f"   ↳ Página vacía o SPA, saltando...")
                continue

            # html2text — limpieza radical
            clean = re.sub(r'<(script|style|nav|footer|head|canvas|svg|noscript|aside)[^>]*>.*?</\1>', ' ', html, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r'<[^>]+>', '\n', clean)
            text = text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
            lines = [l.strip() for l in text.splitlines() if l.strip() and len(l.strip()) > 1]
            # Extracción de canales
            channels: List[Dict[str, str]] = []
            current_cat = "General"
            GENRE_WORDS = ["cine", "peliculas", "series", "deportes", "kids", "niños", "noticias", "news", "musica", "variedades", "nacionales", "internacionales"]

            for line in lines:
                l_low = line.lower()

                # ¿Categoría?
                if 4 < len(line) < 30 and not re.search(r'\d', line):
                    if any(g in l_low for g in GENRE_WORDS):
                        current_cat = line.title()
                        continue

                # Patrón A: "14 Telefé"  /  "1001 HBO HD"
                m1 = re.match(r'^(\d{1,4})\s+([A-Za-záéíóúñÁÉÍÓÚÑ][A-Za-z0-9áéíóúñÁÉÍÓÚÑ\s\.&+\-]{2,28})$', line)
                # Patrón B: "Telefé 14"
                m2 = re.match(r'^([A-Za-záéíóúñÁÉÍÓÚÑ][A-Za-z0-9áéíóúñÁÉÍÓÚÑ\s\.&+\-]{2,28})\s+(\d{1,4})$', line)
                # Patrón C (foros): "Canal 13 - Canal 13" o "Bravo TV - Canal 18"
                m3 = re.match(r'^(.{3,35}?)\s*[-–]\s*[Cc]anal\s+(\d{1,4})', line)

                m = m1 or m2 or m3
                if m:
                    if m3:   c, n = m.group(1).strip(), m.group(2)
                    elif m1: n, c = m.group(1), m.group(2).strip()
                    else:    c, n = m.group(1).strip(), m.group(2)

                    n_int = int(n)
                    if n_int < 1 or n_int > 2000: continue  # números inválidos

                    if not any(bad in c.lower() for bad in JS_TRASH) and not any(x in c for x in "{}[];()"):
                        if not any(ch["c"] == c for ch in channels):
                            channels.append({"n": str(n_int), "c": c, "s": current_cat})

            n_found = len(channels)
            print(f"   ↳ {n_found} canales encontrados en texto plano")

            if n_found > len(best_channels):
                best_channels = list(channels)

            if n_found > 100:
                print(f"🏆 VICTORIA: {n_found} canales extraídos del resultado más reciente.")
                return channels

        except Exception as e:
            print(f"   ↳ Error: {e}")
            continue

    if best_channels:
        print(f"🏆 Mejor resultado: {len(best_channels)} canales.")
        return best_channels

    return None




# ---------------------------------------------------------------------------
# PASO 3: Guardar resultado + actualizar settings.json
# ---------------------------------------------------------------------------
def save_channels(channels: List[Dict[str, str]], provider: str, config_dir: str) -> str:
    """
    Guarda la lista en channels_<proveedor>.json en formato Fina Estándar.
    """
    os.makedirs(config_dir, exist_ok=True)
    slug = provider.lower()
    filename = f"channels_{slug}.json"
    target = os.path.join(config_dir, filename)

    with open(target, "w", encoding="utf-8") as f:
        json.dump(channels, f, indent=4, ensure_ascii=False)

    print(f"✅ {len(channels)} canales guardados en {target}")
    return slug

def update_settings_provider(provider_slug: str, config_dir: str, project_root: Optional[str]) -> None:
    """
    Escribe automáticamente el proveedor detectado en settings.json.
    El usuario no necesita hacer nada — Fina lo registra solo.
    """
    settings_path: str = os.path.join(config_dir, "settings.json")

    # Buscar settings en project_root si no existe en XDG
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
    
    # Actualización segura: creamos una copia limpia de la sección apis
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

def _normalize_channels(data: Any) -> List[Dict[str, str]]:
    """Normaliza lista o dict de canales al formato Fina Standard: [{n, c, s}]"""
    out: List[Dict[str, str]] = []
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                n = str(item.get("n", item.get("number", "")))
                c = str(item.get("c", item.get("name", "")))
                s = str(item.get("s", item.get("section", "General")))
                if n and c: out.append({"n": n, "c": c, "s": s})
    elif isinstance(data, dict):
        for name, number in data.items():
            out.append({"n": str(number), "c": str(name), "s": "General"})
    return out

# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="Escaneo automático de canales para Deco Android TV")
    parser.add_argument("--ip", required=True, help="IP del Decodificador")
    args = parser.parse_args()

    ip: str = str(args.ip)
    project_root: Optional[str] = find_project_root()
    config_dir: str = get_config_dir()

    print(f"\n🚀 Fina Channel Scanner — Deco {ip}\n{'─'*50}")

    # 0. Identificar proveedor
    provider: str = identify_provider(ip)

    # 1. Base de datos interna
    channels: Optional[List[Dict[str, str]]] = scan_internal_db(ip)

    # 2. Web scraping autónomo (Plug & Play)
    if not channels:
        channels = fetch_from_web(provider)

    # 3. Guardar y registrar proveedor
    if channels:
        saved_slug: str = save_channels(channels, provider, config_dir)
        update_settings_provider(saved_slug, config_dir, project_root)
        print(f"\n✅ Escaneo completo. '{saved_slug.capitalize()}' listo para usar.")
    else:
        print("\n❌ No se pudo obtener la lista de canales automáticamente.")
        print("   Sugerencia: conectá Red y volvé a intentar, o usá números de canal directamente.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⏹ Escaneo cancelado.")
    except Exception as fatal:
        print(f"✗ Fatal: {fatal}")
        sys.exit(1)
