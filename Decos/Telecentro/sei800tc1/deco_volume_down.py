#!/usr/bin/env python3
import asyncio
import sys
import os
import argparse

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
try:
    from deco_remote_helper import send_command # type: ignore
except ImportError:
    from .deco_remote_helper import send_command # type: ignore

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bajar Volumen - Deco Telecentro")
    parser.add_argument("--ip", required=True, help="IP del Decodificador")
    args = parser.parse_args()
    try:
        asyncio.run(send_command(args.ip, "volume", "down"))
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"✗ Error: {e}")
        sys.exit(1)
