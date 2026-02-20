import subprocess
import sys
import argparse

def run_command(cmd):
    try:
        subprocess.run(cmd, capture_output=True, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {e}")

def set_volume(ip, volume_level):
    print(f"Connecting to {ip}...")
    run_command(["adb", "connect", ip])
    
    print(f"Setting volume to {volume_level} on {ip}...")
    cmd = ["adb", "-s", f"{ip}:5555", "shell", "media", "volume", "--show", "--stream", "3", "--set", str(volume_level)]
    run_command(cmd)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Set TV Volume')
    parser.add_argument('--ip', default='192.168.0.11', help='TV IP address')
    parser.add_argument('volume', type=int, help='Volume level (0-100)')
    
    # We use parse_known_args in case extra flags are passed, but standard parse_args is fine
    args = parser.parse_args()
    
    set_volume(args.ip, args.volume)
