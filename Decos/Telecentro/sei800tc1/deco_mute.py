import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from remote_helper import send_command
asyncio.run(send_command("192.168.0.9", "key", "VOLUME_MUTE"))
