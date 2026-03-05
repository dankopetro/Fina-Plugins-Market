import subprocess
import sys

def mute_tv():
    ip = "192.168.0.11"
    if "--ip" in sys.argv:
        try:
            ip = sys.argv[sys.argv.index("--ip") + 1]
        except IndexError:
            pass
            
    print(f"Connecting to {ip}...")
    try:
        subprocess.run(["adb", "connect", ip], capture_output=True, timeout=5)
        
        print(f"Muting {ip}...")
        # KEYCODE_MUTE = 164
        subprocess.run(["adb", "-s", f"{ip}:5555", "shell", "input", "keyevent", "164"], capture_output=True, timeout=5)
    except subprocess.TimeoutExpired:
        print(f"⌛ Timeout: La TV en {ip} no responde.")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    mute_tv()
