
import subprocess
import argparse
import sys
import time
import socket

def wake_on_lan(macaddress):
    """Envia un Magic Packet para despertar la TV"""
    if not macaddress or len(macaddress) < 12:
        return False
    macaddress = macaddress.replace(':', '').replace('-', '')
    data = b'f' * 12 + (bytes.fromhex(macaddress) * 16)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    try:
        sock.sendto(data, ('255.255.255.255', 9))
        return True
    except:
        return False
    finally:
        sock.close()

def get_power_state(ip):
    try:
        # Intento de conexión rápido
        subprocess.run(["adb", "connect", ip], capture_output=True, timeout=2)
        cmd = ["adb", "-s", f"{ip}:5555", "shell", "dumpsys", "power"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=2)
        if "mWakefulness=Awake" in result.stdout:
            return "on"
        if "mWakefulness=Asleep" in result.stdout:
            return "off"
    except:
        pass
    return "unknown"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ip", required=True)
    parser.add_argument("--mac", help="MAC para WoL")
    args = parser.parse_args()
    
    # 1. Chequeo inicial
    state = get_power_state(args.ip)
    print(f"📺 Estado de TV {args.ip}: {state}")
    
    if state == "on":
        print("⚡ Apagando TV (Power key)...")
        subprocess.run(["adb", "-s", f"{args.ip}:5555", "shell", "input", "keyevent", "26"], timeout=3)
    else:
        # 2. Si es desconocido o apagado, intentar WoL
        if args.mac:
            print(f"📡 Enviando Magic Packet (WoL) a {args.mac}...")
            wake_on_lan(args.mac)
        
        # 3. Reintentar conexión con paciencia (la TV tarda en levantar la red)
        print("⚡ Esperando que la TV despierte...")
        connected = False
        for i in range(5): # 5 intentos = ~10-15 segundos
            print(f"🔌 Intento de conexión {i+1}...")
            try:
                # Quitamos el timeout de Python y dejamos que ADB maneje su propio timeout interno o usamos uno más largo
                subprocess.run(["adb", "connect", args.ip], capture_output=True, timeout=5)
                # Verificar si realmente conectó
                cmd = ["adb", "-s", f"{args.ip}:5555", "shell", "input", "keyevent", "224"]
                res = subprocess.run(cmd, capture_output=True, timeout=3)
                if res.returncode == 0:
                    print("✅ TV Despertada con éxito.")
                    connected = True
                    break
            except Exception as e:
                print(f"⌛ Aun no responde...")
            
            time.sleep(2)
        
        if not connected:
            print("❌ No se pudo establecer conexión ADB tras el WoL.")

if __name__ == "__main__":
    main()
