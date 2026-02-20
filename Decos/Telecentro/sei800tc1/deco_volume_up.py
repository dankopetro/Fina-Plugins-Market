import asyncio
import sys
import os
# Adjust path to find remote_helper
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from remote_helper import send_command
asyncio.run(send_command("192.168.0.9", "volume", "up"))
