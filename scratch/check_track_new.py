import sys
import os
from pathlib import Path
from mutagen import File
from core.metadata_handler import get_track_info, COVERS_DIR

def check_file(path_str):
    path = Path(path_str)
    print(f"=== Checking actual synced file: {path.name} ===")
    if not path.exists():
        print(f"File {path} does not exist!")
        return
        
    print(f"File size: {path.stat().st_size} bytes")
    
    try:
        audio = File(path)
        if audio is None:
            print("Mutagen returned None for the file!")
            return
            
        print(f"Mutagen type: {type(audio)}")
        print(f"Tags keys: {list(audio.tags.keys()) if audio.tags else 'None'}")
        
        # Check for APIC
        if audio.tags:
            apic_keys = [k for k in audio.tags.keys() if k.startswith("APIC")]
            print(f"APIC tags found: {apic_keys}")
            for k in apic_keys:
                apic_tag = audio.tags[k]
                print(f"  APIC key: {k}, mime: {apic_tag.mime}, type: {apic_tag.type}, desc: {apic_tag.desc}, size: {len(apic_tag.data)} bytes")
                
        # Check for pictures
        if hasattr(audio, "pictures") and audio.pictures:
            print(f"Pictures found: {len(audio.pictures)}")
            for i, pic in enumerate(audio.pictures):
                print(f"  Picture {i}, mime: {pic.mime}, type: {pic.type}, desc: {pic.desc}, size: {len(pic.data)} bytes")
                
        # Run get_track_info
        info = get_track_info(path)
        print(f"\n--- get_track_info output ---")
        print(f"title: {info.get('title')}")
        print(f"artist: {info.get('artist')}")
        print(f"album: {info.get('album')}")
        print(f"cover_path: {info.get('cover_path')}")
        
        cover_path = info.get('cover_path')
        if cover_path:
            cover_file = Path(cover_path)
            if cover_file.exists():
                print(f"✅ Cover successfully saved and exists on disk! Size: {cover_file.stat().st_size} bytes")
            else:
                print(f"❌ Cover file was not written or does not exist at: {cover_path}")
                
    except Exception as e:
        print(f"Error checking file: {e}")

if __name__ == "__main__":
    check_file("/Users/apfanom/.audaci/telegram_music/01. Drake - Rusty Intro.mp3")
