import subprocess
import argparse
from typing import Optional, List, Any

def switch_to_tv(ip: str) -> None:
    print(f"📺 Cambiando a TV/Aire en {ip}...")
    try:
        # Asegurar conexión
        subprocess.run(["adb", "connect", f"{ip}:5555"], capture_output=True, timeout=3) # type: ignore
        
        # MODO HACKER: Salto Directo a Sintonizador de Aire
        print("📡 Saltando Directo a TV/Aire...")
        # Usamos el Intent que confirmamos que funciona de forma instantánea
        subprocess.run(["adb", "-s", f"{ip}:5555", "shell", "am", "start", "-a", "android.intent.action.VIEW", "-d", "content://android.media.tv/channel/0", "-n", "com.tcl.tv/.TVActivity"], timeout=5) # type: ignore
        
        print("🚀 Salto Instantáneo a TV completado.")

    except Exception as e:
        print(f"❌ Error: {e}")

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ip", required=True, help="IP del dispositivo")
    parser.add_argument("--mac", help="MAC (opcional)")
    args, _ = parser.parse_known_args()
    
    target_ip: Optional[str] = getattr(args, 'ip', None)
    
    if target_ip:
        switch_to_tv(target_ip)
    else:
        print("❌ Faltan argumentos: --ip")

if __name__ == "__main__":
    main()
