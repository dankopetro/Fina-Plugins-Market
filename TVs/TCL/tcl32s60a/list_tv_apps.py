import subprocess
import sys
import json
import os

# Define local configuration path explicitly
SETTINGS_FILE = "./config/settings.json"

def get_target_ip():
    if "--ip" in sys.argv:
        try:
            return sys.argv[sys.argv.index("--ip") + 1]
        except IndexError:
            pass
    return None

def update_settings_apps_comprehensive(found_apps):
    """Actualiza settings.json reemplazando la lista completa de apps"""
    print(f"📂 Usando configuración: {SETTINGS_FILE}")
    
    if not os.path.exists(SETTINGS_FILE):
        try:
            os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
            with open(SETTINGS_FILE, 'w') as f:
                json.dump({"tv_apps": {}}, f)
        except Exception as e:
             print(f"No se pudo crear archivo de configuración: {e}")
             return

    try:
        with open(SETTINGS_FILE, 'r') as f:
            data = json.load(f)
        
        # Override with comprehensive found apps
        data["tv_apps"] = found_apps
        
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(data, f, indent=2)
            
        print(f"✅ Configuración actualizada. {len(found_apps)} apps guardadas.")
    except Exception as e:
        print(f"Error actualizando settings: {e}")

def get_app_name_heuristic(pkg):
    """Heurística para extraer un nombre legible del paquete"""
    # Filtros para ignorar ruido de sistema
    if any(x in pkg for x in ["android.", "google.", "tcl.", "mediatek.", "realtek.", "android.auto"]):
        return None
        
    parts = pkg.split('.')
    if len(parts) < 2: return pkg.capitalize()
    
    # Usualmente el nombre es la última o penúltima parte
    name = parts[-1].capitalize()
    if name in ["Android", "Tv", "Launcher", "Main", "Player"]:
        name = parts[-2].capitalize()
        
    return name

def list_packages():
    """Enumera todos los paquetes instalados en el dispositivo conectado"""
    ip = get_target_ip()
    if not ip:
        print("Error: No se proporcionó IP (--ip)")
        return
    
    print(f"Connecting to {ip}...")
    try:
        # Force connect
        subprocess.run(['adb', 'connect', ip], capture_output=True, timeout=5)
    except Exception as e:
        print(f"Error connecting to ADB: {e}")
        return

    print(f"Listando paquetes de {ip}...")
    try:
        # Solo listamos apps de terceros que tengan launcher intent (esto filtra mucho ruido)
        # Pero a veces 'pm list packages -3' es más confiable para lo que quiere el usuario
        cmd = ['adb', '-s', f'{ip}:5555', 'shell', 'pm', 'list', 'packages', '-3']
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        
        if res.returncode != 0:
            print(f"Error ADB Output: {res.stderr}")
            return

        all_pkgs = res.stdout.splitlines()
        
        found_apps = {}
        print(f"\n--- APPS DETECTADAS en {ip} ---")
        
        for line in all_pkgs:
            pkg = line.replace('package:', '').strip()
            if not pkg: continue
            
            # Heurística para todos los paquetes -3
            name = get_app_name_heuristic(pkg)
            
            if name:
                print(f"✓ {name}: {pkg}")
                found_apps[name] = pkg

        if found_apps:
            update_settings_apps_comprehensive(found_apps)
        else:
            print("No new apps found.")
                
    except Exception as e:
        print(f"Error listando paquetes: {e}")

if __name__ == "__main__":
    list_packages()
