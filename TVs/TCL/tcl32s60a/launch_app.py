import subprocess
import argparse
import sys

from typing import Optional

def launch_app() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ip", help="IP address of the TV", required=True)
    parser.add_argument("--package", required=True, help="Package name of the app to launch")
    args = parser.parse_args()
    
    target_ip: str = args.ip
    package: str = args.package

    print(f"Launching {package} on {target_ip}...")
    try:
        subprocess.run(["adb", "connect", f"{target_ip}:5555"], capture_output=True, timeout=5) # type: ignore
        # monkey is a reliable way to start an app by package name
        cmd = ["adb", "-s", f"{target_ip}:5555", "shell", "monkey", "-p", package, "-c", "android.intent.category.LAUNCHER", "1"]
        subprocess.run(cmd, capture_output=True, timeout=5) # type: ignore
        print("Done.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    launch_app()
