
import pystray
from PIL import Image
import threading
import time
import os

def on_quit(icon, item):
    icon.stop()

# Create a simple icon
image = Image.new('RGB', (64, 64), color='red')
icon = pystray.Icon("test_icon", image, "Test Icon", menu=pystray.Menu(
    pystray.MenuItem("Quit", on_quit)
))

print("Starting tray detached...")
try:
    icon.run_detached()
    print("Tray started detached.")
except Exception as e:
    print(f"Error starting detached: {e}")

print("Waiting 10 seconds...")
time.sleep(10)
print("Stopping...")
icon.stop()
print("Done.")
