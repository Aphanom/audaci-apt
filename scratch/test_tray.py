
import pystray
from PIL import Image
import threading
import time
import os

def on_quit(icon, item):
    icon.stop()

def run_tray():
    # Create a simple icon
    image = Image.new('RGB', (64, 64), color='red')
    icon = pystray.Icon("test_icon", image, "Test Icon", menu=pystray.Menu(
        pystray.MenuItem("Quit", on_quit)
    ))
    icon.run()

print("Starting tray thread...")
t = threading.Thread(target=run_tray)
t.daemon = True
t.start()

print("Tray started (hopefully). Waiting 10 seconds...")
time.sleep(10)
print("Done.")
