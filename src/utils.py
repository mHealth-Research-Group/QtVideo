import json
import os
from pathlib import Path
import tempfile
from typing import List, Optional, Tuple
from src.models import TimelineAnnotation

class AutosaveManager:
    def __init__(self, interval: int = 300000) -> None: 
        """Initialize autosave manager"""
        self.interval = interval
        self.autosave_dir = os.path.join(tempfile.gettempdir(), 'video_annotator_autosave')
        os.makedirs(self.autosave_dir, exist_ok=True)

    def calculate_video_hash(self, file_path: str) -> int:
        """Calculate hash from video file size"""
        try:
            file_size = os.path.getsize(file_path)
            size_str = str(file_size)
            video_hash = 0
            
            for char in size_str:
                video_hash = ((video_hash << 5) - video_hash + ord(char))
                video_hash = video_hash & video_hash 
            
            return video_hash
        except Exception as e:
            print(f"Error calculating video hash: {str(e)}")
            return 0

    def delete_autosave(self, video_path: str) -> None:
        """Delete autosave file for the given video"""
        if not video_path:
            return
            
        try:
            video_name = Path(video_path).stem
            autosave_path = os.path.join(self.autosave_dir, f"{video_name}_autosave.json")
            if os.path.exists(autosave_path):
                os.remove(autosave_path)
        except Exception as e:
            print(f"Error deleting autosave: {str(e)}")

    def save_annotations(self, video_path: str, annotations: List[TimelineAnnotation], *, video_hash: int = 0) -> None:
        """Save annotations to autosave file"""
        if not video_path:
            return
            
        try:
            video_name = Path(video_path).stem
            autosave_path = os.path.join(self.autosave_dir, f"{video_name}_autosave.json")
            
            annotations_data = {
                "annotations": [],
                "videohash": video_hash,
                "video_path": video_path
            }
            
            for annotation in annotations:
                annotations_data["annotations"].append({
                    "id": annotation.id,
                    "range": {
                        "start": annotation.start_time,
                        "end": annotation.end_time
                    },
                    "shape": annotation.shape,
                    "comments": annotation.comments
                })
                
            with open(autosave_path, 'w') as f:
                json.dump(annotations_data, f, indent=4)
        except Exception as e:
            print(f"Autosave failed: {str(e)}")
            
    def check_for_autosave(self, video_path: str, current_hash: int) -> Tuple[Optional[dict], bool]:
        """
        Check for and load autosave file
        Returns: Tuple of (data dict, hash_matches)
                data dict is None if no autosave found
                hash_matches is True if video hash matches autosave
        """
        if not video_path:
            return None, False
            
        video_name = Path(video_path).stem
        autosave_path = os.path.join(self.autosave_dir, f"{video_name}_autosave.json")
        
        if os.path.exists(autosave_path):
            try:
                with open(autosave_path, 'r') as f:
                    data = json.load(f)
                if data.get("video_path") == video_path:
                    saved_hash = data.get("videohash", 0)
                    return data, saved_hash == current_hash
            except Exception as e:
                print(f"Failed to load autosave: {str(e)}")
        
        return None, False
