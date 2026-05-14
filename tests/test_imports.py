import pytest

def test_imports():
    import PIL
    from PIL import Image
    import flet
    import vlc
    import mutagen
    import rapidfuzz
    import colorthief
    import vosk
    import sounddevice
    import numpy
    import watchdog
    import requests
    import pystray
    import aiogram
    import fastapi
    import uvicorn
    
    print("All imports successful!")

def test_pil_imaging():
    # This specifically checks if PIL's C extensions work
    from PIL import Image, _imaging
    img = Image.new('RGB', (10, 10))
    assert img.size == (10, 10)
