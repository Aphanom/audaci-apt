
import pystray
from PIL import Image
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
icon.run_detached()
print("Tray started detached.")

print("Starting a 'main loop' simulation (like Flet)...")
for i in range(10):
    print(f"Loop iteration {i}")
    time.sleep(1)

print("Stopping tray...")
icon.stop()
print("Done.")
