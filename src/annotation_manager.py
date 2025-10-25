from PyQt6.QtWidgets import QMessageBox
from PyQt6.QtCore import QTimer
from src.dialogs import AnnotationDialog
from src.models import TimelineAnnotation
import random
import json
from src.utils import autosave

class AnnotationManager:
    def __init__(self, app):
        self.app = app
        self.last_used_labels = {
            "posture": "",
            "hlb": [],
            "pa_type": "",
            "behavioral_params": [],
            "exp_situation": "",
            "special_notes": ""
        }
        self.posture_colors = {}

    def get_posture_color(self, posture):
        if posture is None or posture == "":
             return "#808080"
        if posture not in self.posture_colors:
            while True:
                r = random.randint(100, 230)
                g = random.randint(100, 230)
                b = random.randint(100, 230)
                if abs(r - g) > 20 or abs(g - b) > 20 or abs(b - r) > 20:
                    color = f"#{r:02x}{g:02x}{b:02x}"
                    if color not in self.posture_colors.values():
                        break
            self.posture_colors[posture] = color
        return self.posture_colors[posture]

    def check_overlap(self, start_time, end_time, exclude_annotation=None):
        tolerance = 0.001
        for annotation in self.app.annotations:
            if annotation == exclude_annotation:
                continue
            if (start_time < (annotation.end_time - tolerance) and
                    end_time > (annotation.start_time + tolerance)):
                return True
        return False

    def get_current_annotation_index(self, sorted_annotations=None):
        current_time = self.app.media_player['_position'] / 1000.0
        if sorted_annotations is None:
            sorted_annotations = sorted(self.app.annotations, key=lambda x: x.start_time)

        for i, annotation in enumerate(sorted_annotations):
            tolerance = 0.001
            if (annotation.start_time - tolerance) <= current_time <= (annotation.end_time + tolerance):
                return i
        return -1

    @autosave
    def toggleAnnotation(self):
        current_time = self.app.media_player['_position'] / 1000.0

        if self.app.current_annotation is None:
            if self.check_overlap(current_time, current_time):
                QMessageBox.warning(self.app, "Overlap Detected",
                                    "Cannot start an annotation within an existing one.")
                return

            self.app.current_annotation = TimelineAnnotation(start_time=current_time)
            temp_labels = self.last_used_labels.copy()
            temp_labels["special_notes"] = ""
            self.app.current_annotation.update_comment_body(**temp_labels)
            print(f"Started annotation at {current_time:.3f}s with last used labels")
            self.app.updateAnnotationTimeline()

        else:
            start_time = self.app.current_annotation.start_time
            if current_time <= start_time:
                QMessageBox.warning(self.app, "Invalid End Time",
                                    "End time must be after the start time.")
                return

            if self.check_overlap(start_time, current_time, exclude_annotation=self.app.current_annotation):
                QMessageBox.warning(self.app, "Overlap Detected",
                                    "Annotations cannot overlap.")
                return

            self.app.current_annotation.end_time = current_time

            try:
                if self.app.current_annotation.comments:
                    body_data = json.loads(self.app.current_annotation.comments[0].get("body", "[]"))
                    data_map = {item.get("category"): item.get("selectedValue") for item in body_data}
                    self.last_used_labels = {
                        "posture": data_map.get("POSTURE", ""),
                        "hlb": data_map.get("HIGH LEVEL BEHAVIOR", []),
                        "pa_type": data_map.get("PA TYPE", ""),
                        "behavioral_params": data_map.get("Behavioral Parameters", []),
                        "exp_situation": data_map.get("Experimental situation", ""),
                        "special_notes": ""
                    }
            except json.JSONDecodeError as e:
                print(f"Error decoding comment body for storing last labels: {e}")


            self.app.annotations.append(self.app.current_annotation)
            self.app.annotations.sort(key=lambda x: x.start_time)
            print(f"Finished annotation: {start_time:.3f}s - {current_time:.3f}s")
            self.app.current_annotation = None
            self.app.updateAnnotationTimeline()


    @autosave
    def editAnnotation(self):
        sorted_annotations = sorted(self.app.annotations, key=lambda x: x.start_time)
        current_idx = self.get_current_annotation_index(sorted_annotations)

        target_annotation = None
        if current_idx != -1:
            target_annotation = sorted_annotations[current_idx]
        elif self.app.current_annotation:
            target_annotation = self.app.current_annotation

        dialog = AnnotationDialog(target_annotation, self.app)

        if dialog.exec():
            selections = dialog.get_all_selections()
            label_data = {
                "posture": selections["POSTURE"],
                "hlb": selections["HIGH LEVEL BEHAVIOR"],
                "pa_type": selections["PA TYPE"],
                "behavioral_params": selections["Behavioral Parameters"],
                "exp_situation": selections["Experimental situation"],
                "special_notes": selections["Special Notes"]
            }

            if target_annotation:
                target_annotation.update_comment_body(**label_data)
                self.last_used_labels = label_data.copy()
                self.last_used_labels["special_notes"] = ""
                print(f"Updated labels for annotation: {target_annotation.start_time:.3f}s")
                self.app.updateAnnotationTimeline()
            else:
                self.last_used_labels = label_data.copy()
                self.last_used_labels["special_notes"] = ""
                print("Updated default labels for next annotation.")

    @autosave
    def cancelAnnotation(self):
        if self.app.current_annotation is not None:
            print("Canceled annotation creation.")
            self.app.current_annotation = None
            self.app.updateAnnotationTimeline()

    @autosave
    def deleteCurrentLabel(self):
        sorted_annotations = sorted(self.app.annotations, key=lambda x: x.start_time)
        current_idx = self.get_current_annotation_index(sorted_annotations)

        if current_idx != -1:
            annotation_to_delete = sorted_annotations[current_idx]
            confirm = QMessageBox.question(self.app, "Confirm Delete",
                                           f"Delete annotation from {annotation_to_delete.start_time:.2f}s to {annotation_to_delete.end_time:.2f}s?",
                                           QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                           QMessageBox.StandardButton.No)

            if confirm == QMessageBox.StandardButton.Yes:
                try:
                    self.app.annotations.remove(annotation_to_delete)
                    self.app.updateAnnotationTimeline()
                    print(f"Deleted annotation: {annotation_to_delete.start_time:.2f}s - {annotation_to_delete.end_time:.2f}s")
                except ValueError:
                     print("Error: Annotation to delete not found in main list.")
        else:
             QMessageBox.information(self.app, "Delete Label", "The playback position is not currently inside any annotation.")


    def moveToPreviousLabel(self):
        if not self.app.annotations:
            return
        boundary_points = sorted(list(set(
            p for ann in self.app.annotations for p in (ann.start_time, ann.end_time)
        )))

        current_time = self.app.media_player['_position'] / 1000.0
        target_time = -1
        tolerance = 0.05

        for point in reversed(boundary_points):
            if point < current_time - tolerance:
                target_time = point
                break
        else:
            target_time = 0

        if target_time != -1:
            self.app.setPosition(int(target_time * 1000))

    def moveToNextLabel(self):
        if not self.app.annotations:
            return
        boundary_points = sorted(list(set(
            p for ann in self.app.annotations for p in (ann.start_time, ann.end_time)
        )))

        current_time = self.app.media_player['_position'] / 1000.0
        target_time = -1
        tolerance = 0.05
        for point in boundary_points:
            if point > current_time + tolerance:
                target_time = point
                break

        if target_time != -1:
            self.app.setPosition(int(target_time * 1000))

    @autosave
    def mergeWithPrevious(self):
        sorted_annotations = sorted(self.app.annotations, key=lambda x: x.start_time)
        current_idx = self.get_current_annotation_index(sorted_annotations)
        print("Current index of annotation being merged:", current_idx, sorted_annotations[current_idx] if current_idx != -1 else None)
        if current_idx == -1:
            QMessageBox.information(self.app, "Merge Failed", "Cannot merge: No annotation at the current position.")
            return

        if current_idx == 0:
            QMessageBox.information(self.app, "Merge Failed", "Cannot merge: No previous annotation exists.")
            return

        current_annotation = sorted_annotations[current_idx]
        prev_annotation = sorted_annotations[current_idx - 1]
        gap = current_annotation.start_time - prev_annotation.end_time
        if abs(gap) > 0.1:
            QMessageBox.warning(self.app, "Invalid Merge", f"Cannot merge: Annotations are not adjacent (Gap: {gap:.3f}s).")
            return

        merged_annotation = TimelineAnnotation(
            start_time=prev_annotation.start_time,
            end_time=current_annotation.end_time
        )
        if current_annotation.comments:
            merged_annotation.copy_comments_from(current_annotation)
        elif prev_annotation.comments:
            merged_annotation.copy_comments_from(prev_annotation)

        try:
            annotations_to_remove_ids = {current_annotation.id, prev_annotation.id}
            self.app.annotations = [ann for ann in self.app.annotations if ann.id not in annotations_to_remove_ids]

        except ValueError:
             print("Error: Could not remove original annotations during merge.")
             return

        self.app.annotations.append(merged_annotation)
        self.app.annotations.sort(key=lambda x: x.start_time)
        print(f"Merged annotations into: {merged_annotation.start_time:.3f}s - {merged_annotation.end_time:.3f}s")
        self.app.updateAnnotationTimeline()

    @autosave
    def mergeWithNext(self):
        sorted_annotations = sorted(self.app.annotations, key=lambda x: x.start_time)
        current_idx = self.get_current_annotation_index(sorted_annotations)
        if current_idx == -1 or current_idx >= len(sorted_annotations) - 1:
            QMessageBox.information(self.app, "Merge Failed", "Cannot merge: No annotation at current position or no next annotation exists.")
            return

        current_annotation = sorted_annotations[current_idx]
        next_annotation = sorted_annotations[current_idx + 1]

        gap = next_annotation.start_time - current_annotation.end_time
        if abs(gap) > 0.1:
            QMessageBox.warning(self.app, "Invalid Merge", f"Cannot merge: Annotations are not adjacent (Gap: {gap:.3f}s).")
            return

        merged_annotation = TimelineAnnotation(
            start_time=current_annotation.start_time,
            end_time=next_annotation.end_time
        )

        if current_annotation.comments:
            merged_annotation.copy_comments_from(current_annotation)
        elif next_annotation.comments:
            merged_annotation.copy_comments_from(next_annotation)

        try:
            annotations_to_remove_ids = {current_annotation.id, next_annotation.id}
            self.app.annotations = [ann for ann in self.app.annotations if ann.id not in annotations_to_remove_ids]
        except ValueError:
             print("Error: Could not remove original annotations during merge.")
             return

        self.app.annotations.append(merged_annotation)
        self.app.annotations.sort(key=lambda x: x.start_time)
        print(f"Merged annotations into: {merged_annotation.start_time:.3f}s - {merged_annotation.end_time:.3f}s")
        self.app.updateAnnotationTimeline()

    @autosave
    def splitCurrentLabel(self):
        current_time = self.app.media_player['_position'] / 1000.0
        sorted_annotations = sorted(self.app.annotations, key=lambda x: x.start_time)
        current_idx = self.get_current_annotation_index(sorted_annotations)

        if current_idx == -1:
            QMessageBox.information(self.app, "Split Failed", "Cannot split: Playhead is not inside an annotation.")
            return

        annotation_to_split = sorted_annotations[current_idx]
        min_duration = 0.1
        if not (annotation_to_split.start_time < current_time < annotation_to_split.end_time):
             QMessageBox.warning(self.app, "Invalid Split", "Split point must be strictly inside the annotation.")
             return
        if (current_time - annotation_to_split.start_time < min_duration or
                annotation_to_split.end_time - current_time < min_duration):
            QMessageBox.warning(self.app, "Invalid Split", f"Split results in segment smaller than {min_duration}s.")
            return

        new_annotation = TimelineAnnotation(
            start_time=current_time,
            end_time=annotation_to_split.end_time
        )
        new_annotation.copy_comments_from(annotation_to_split)
        original_end_time = annotation_to_split.end_time
        annotation_to_split.end_time = current_time
        self.app.annotations.append(new_annotation)
        self.app.annotations.sort(key=lambda x: x.start_time)
        print(f"Split annotation {annotation_to_split.start_time:.3f}s-{original_end_time:.3f}s at {current_time:.3f}s")
        self.app.updateAnnotationTimeline()