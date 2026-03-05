import subprocess
import argparse
import sys

def launch_app():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ip", help="IP address of the TV", required=True)
    parser.add_argument("--package", required=True, help="Package name of the app to launch")
    args = parser.parse_args()
    
    ip = args.ip
    package = args.package

    print(f"Launching {package} on {ip}...")
    try:
        subprocess.run(["adb", "connect", ip], capture_output=True, timeout=5)
        # monkey is a reliable way to start an app by package name
        cmd = ["adb", "-s", f"{ip}:5555", "shell", "monkey", "-p", package, "-c", "android.intent.category.LAUNCHER", "1"]
        subprocess.run(cmd, capture_output=True, timeout=5)
        print("Done.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    launch_app()
