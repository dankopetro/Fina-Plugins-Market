import subprocess
import os
import sys

def send_key(key):
    ip = None
    if "--ip" in sys.argv:
        ip = sys.argv[sys.argv.index("--ip") + 1]
    
    if not ip:
        print("Error: IP no especificada (--ip)")
        sys.exit(1)
    
    try:
        subprocess.run(["adb", "connect", ip], capture_output=True, timeout=5)
        subprocess.run(["adb", "-s", f"{ip}:5555", "shell", "input", "keyevent", key], capture_output=True, timeout=5)
    except subprocess.TimeoutExpired:
        print(f"⌛ Timeout: La TV en {ip} no responde.")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    send_key("KEYCODE_VOLUME_DOWN")
