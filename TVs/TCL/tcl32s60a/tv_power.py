import subprocess
import argparse
import sys
import time
import socket
from typing import Optional, List, Any

def wake_on_lan(mac_address: str) -> bool:
    """Envía un Magic Packet para despertar la TV vía WoL"""
    try:
        # Limpiar MAC
        mac: str = mac_address.replace(":", "").replace("-", "").strip()
        if len(mac) != 12:
            return False
            
        data: bytes = b'f' * 12 + (bytes.fromhex(mac) * 16)
        
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.sendto(data, ("255.255.255.255", 9))
        return True
    except Exception as e:
        print(f"⚠️ Error enviando WoL: {e}")
        return False

def get_power_state(ip: str) -> str:
    """Obtiene el estado de energía actual de la TV vía ADB"""
    target: str = f"{ip}:5555" if ":" not in ip else ip
    try:
        # Intento de conexión rápido
        subprocess.run(["adb", "connect", target], capture_output=True, timeout=2) # type: ignore
        cmd: List[str] = ["adb", "-s", target, "shell", "dumpsys", "power"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=2) # type: ignore
        if "mWakefulness=Awake" in str(result.stdout):
            return "on"
        if "mWakefulness=Asleep" in str(result.stdout):
            return "off"
    except Exception:
        pass
    return "unknown"

def main() -> None:
    """Función principal de control de energía"""
    parser = argparse.ArgumentParser(description="Control de energía inteligente para TV TCL")
    parser.add_argument("--ip", required=True, help="IP de la TV")
    parser.add_argument("--mac", help="MAC para WoL")
    args = parser.parse_args()
    
    target_ip: str = str(args.ip)
    target_mac: Optional[str] = args.mac
    
    # 1. Chequeo inicial de estado
    state: str = get_power_state(target_ip)
    print(f"📺 Estado detectado para {target_ip}: {state}")
    
    target_adb: str = f"{target_ip}:5555" if ":" not in target_ip else target_ip

    if state == "on":
        print("⚡ Apagando TV (Power Key)...")
        # KEYCODE_POWER = 26
        subprocess.run(["adb", "-s", target_adb, "shell", "input", "keyevent", "26"], capture_output=True, timeout=3) # type: ignore
        print("✓ Comando de apagado enviado.")
    else:
        # 2. Si es desconocido o apagado, intentar despertar
        if target_mac:
            print(f"📡 Enviando Magic Packet (WoL) a {target_mac}...")
            wake_on_lan(target_mac)
        
        # 3. Intentar comandos de despertar con reintentos
        print("⚡ Despertando TV...")
        connected: bool = False
        for i in range(5):
            print(f"🔌 Intento {i+1} de conexión...")
            try:
                subprocess.run(["adb", "connect", target_adb], capture_output=True, timeout=3) # type: ignore
                # KEYCODE_WAKEUP = 224
                cmd_wakeup: List[str] = ["adb", "-s", target_adb, "shell", "input", "keyevent", "224"]
                res = subprocess.run(cmd_wakeup, capture_output=True, timeout=2) # type: ignore
                if res.returncode == 0:
                    print("✅ TV Despertada con éxito.")
                    connected = True
                    break
            except Exception:
                pass
            time.sleep(2)
        
        if not connected:
            print("❌ No se pudo confirmar el encendido tras los reintentos.")
            sys.exit(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    except Exception as fatal:
        print(f"✗ Fatal: {fatal}")
        sys.exit(1)
