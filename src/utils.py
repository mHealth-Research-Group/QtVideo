import json
import os
from pathlib import Path
import tempfile
from typing import List, Optional, Tuple, Dict
from src.models import TimelineAnnotation
import traceback

class AutosaveManager:
    def __init__(self, interval: int = 300000) -> None:
        self.interval = interval
        self.autosave_dir = os.path.join(tempfile.gettempdir(), 'video_annotator_autosave')
        os.makedirs(self.autosave_dir, exist_ok=True)

    def calculate_video_hash(self, file_path: str) -> int:
        try:
            file_size = os.path.getsize(file_path)
            size_str = str(file_size)
            video_hash = 0
            for char in size_str:
                video_hash = ((video_hash << 5) - video_hash + ord(char))
                video_hash = video_hash & video_hash
            return video_hash
        except Exception as e:
            print(f"Error calculating video hash: {e}")
            return 0

    def delete_autosave(self, video_path: str) -> None:
        if not video_path: return
        try:
            video_name = Path(video_path).stem
            autosave_path = os.path.join(self.autosave_dir, f"{video_name}_autosave.json")
            if os.path.exists(autosave_path):
                os.remove(autosave_path)
        except Exception as e:
            print(f"Error deleting autosave: {e}")

    def save_annotations(self, video_path: str, annotation_sets: Dict[str, dict], *, video_hash: int = 0) -> None:
        if not video_path: return
        try:
            video_name = Path(video_path).stem
            autosave_path = os.path.join(self.autosave_dir, f"{video_name}_autosave.json")
            
            autosave_data = {
                "annotation_sets": {},
                "timeline_order": list(annotation_sets.keys()),
                "videohash": video_hash,
                "video_path": video_path
            }
            
            for key, data in annotation_sets.items():
                serializable_annotations = []
                for ann in data['annotations']:
                    serializable_annotations.append({
                        "id": ann.id,
                        "range": {"start": ann.start_time, "end": ann.end_time},
                        "shape": ann.shape,
                        "comments": ann.comments
                    })
                autosave_data["annotation_sets"][key] = {
                    'name': data['name'],
                    'annotations': serializable_annotations
                }
                
            with open(autosave_path, 'w') as f:
                json.dump(autosave_data, f, indent=4)
            
            print(f"Autosave successful: {len(autosave_data['annotation_sets'])} timeline(s) saved.")

        except Exception as e:
            print("--- AUTOSAVE FAILED ---")
            print(f"An error occurred during the autosave process: {e}")
            traceback.print_exc()
            
    def check_for_autosave(self, video_path: str, current_hash: int) -> Tuple[Optional[dict], bool]:
        if not video_path: return None, False
        video_name = Path(video_path).stem
        autosave_path = os.path.join(self.autosave_dir, f"{video_name}_autosave.json")
        if os.path.exists(autosave_path):
            try:
                with open(autosave_path, 'r') as f: data = json.load(f)
                if data.get("video_path") == video_path:
                    saved_hash = data.get("videohash", 0)
                    return data, saved_hash == current_hash
            except Exception as e:
                print(f"Failed to load autosave file: {e}")
        return None, False
    
def autosave(func):
    def wrapper(self, *args, **kwargs):
        func(self, *args, **kwargs)
        if hasattr(self, 'app') and hasattr(self.app, 'autosave_manager'):
            self.app.autosave()
    return wrapper