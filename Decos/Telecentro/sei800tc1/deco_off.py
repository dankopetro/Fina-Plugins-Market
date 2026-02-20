
import asyncio
import argparse
from remote_helper import send_command

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ip", required=True)
    args = parser.parse_args()
    await send_command(args.ip, "power_off")

if __name__ == "__main__":
    asyncio.run(main())
