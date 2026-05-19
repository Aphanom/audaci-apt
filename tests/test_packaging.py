import os
import sys
import importlib
from unittest import mock
from pathlib import Path
import pytest

def test_requirements_imports():
    """
    Verify that all critical libraries specified in requirements.txt
    can be imported successfully in the current environment.
    """
    required_packages = [
        "flet",
        "mutagen",
        "rapidfuzz",
        "colorthief",
        "Pillow",
        "numpy",
        "watchdog",
        "requests",
        "aiogram",
        "fastapi",
        "uvicorn",
        "dotenv"
    ]
    
    for pkg in required_packages:
        try:
            # Handle special package naming differences
            module_name = "PIL" if pkg == "Pillow" else pkg
            module_name = "dotenv" if pkg == "python-dotenv" else module_name
            importlib.import_module(module_name)
        except ImportError as e:
            pytest.fail(f"Failed to import required package '{pkg}': {e}")


def test_setup_vlc_paths_windows():
    """
    Test setup_vlc_paths on Windows environment mocks.
    """
    from core.player import setup_vlc_paths
    
    # We clear existing environments
    os.environ.pop("PYTHON_VLC_LIB_PATH", None)
    os.environ.pop("PYTHON_VLC_MODULE_PATH", None)
    
    # Mock platform as Windows and frozen state (like executable)
    with mock.patch("sys.platform", "win32"), \
         mock.patch("sys.executable", "C:/Program Files/Audaci/Audaci.exe"), \
         mock.patch("sys.frozen", True, create=True), \
         mock.patch.object(Path, "exists", return_value=True), \
         mock.patch("os.add_dll_directory", create=True) as mock_add_dll:
         
        setup_vlc_paths()
        
        # Resolve path to ensure correct slash types depending on test runner OS
        expected_lib = str(Path("C:/Program Files/Audaci/vlc/libvlc.dll"))
        expected_module = str(Path("C:/Program Files/Audaci/vlc/plugins"))
        expected_dir = str(Path("C:/Program Files/Audaci/vlc"))
        
        assert os.environ.get("PYTHON_VLC_LIB_PATH") == expected_lib
        assert os.environ.get("PYTHON_VLC_MODULE_PATH") == expected_module
        mock_add_dll.assert_called_once_with(expected_dir)


def test_setup_vlc_paths_macos():
    """
    Test setup_vlc_paths on macOS environment mocks.
    """
    from core.player import setup_vlc_paths
    
    os.environ.pop("PYTHON_VLC_LIB_PATH", None)
    os.environ.pop("PYTHON_VLC_MODULE_PATH", None)
    
    with mock.patch("sys.platform", "darwin"), \
         mock.patch("sys.executable", "/Applications/Audaci.app/Contents/MacOS/Audaci"), \
         mock.patch("sys.frozen", True, create=True), \
         mock.patch.object(Path, "exists", return_value=True):
         
        setup_vlc_paths()
        
        assert os.environ.get("PYTHON_VLC_LIB_PATH") == "/Applications/Audaci.app/Contents/MacOS/vlc/libvlc.dylib"
        assert os.environ.get("PYTHON_VLC_MODULE_PATH") == "/Applications/Audaci.app/Contents/MacOS/vlc/plugins"


def test_setup_vlc_paths_linux():
    """
    Test setup_vlc_paths on Linux environment mocks.
    """
    from core.player import setup_vlc_paths
    
    os.environ.pop("PYTHON_VLC_LIB_PATH", None)
    os.environ.pop("PYTHON_VLC_MODULE_PATH", None)
    
    with mock.patch("sys.platform", "linux"), \
         mock.patch("sys.executable", "/usr/local/bin/audaci"), \
         mock.patch("sys.frozen", True, create=True), \
         mock.patch.object(Path, "exists", return_value=True):
         
        setup_vlc_paths()
        
        assert os.environ.get("PYTHON_VLC_LIB_PATH") == "/usr/local/bin/vlc/libvlc.so.5"
        assert os.environ.get("PYTHON_VLC_MODULE_PATH") == "/usr/local/bin/vlc/plugins"
