from PyQt6.QtWidgets import QMessageBox
from src.dialogs import AnnotationDialog
from src.models import TimelineAnnotation
import random
from src.utils import autosave

class AnnotationManager:
    def __init__(self, app):
        self.app = app
        self.default_labels = {
            "posture": "",
            "hlb": [],
            "pa_type": "",
            "behavioral_params": [], "exp_situation": "", "special_notes": ""
        }
        self.posture_colors = {} # Cache for consistent posture colors

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
        return -1 # Return -1 if no annotation contains the current time

    @autosave
    def toggleAnnotation(self):
        current_time = self.app.media_player['_position'] / 1000.0 

        if self.app.current_annotation is None:
            if self.check_overlap(current_time, current_time):
                QMessageBox.warning(self.app, "Overlap Detected",
                                    "Cannot start an annotation within an existing one.")
                return

            self.app.current_annotation = TimelineAnnotation(start_time=current_time)
            self.app.current_annotation.update_comment_body(**self.default_labels)
            print(f"Started annotation at {current_time:.3f}s")
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
            self.app.annotations.append(self.app.current_annotation)
            self.app.annotations.sort(key=lambda x: x.start_time)
            print(f"Finished annotation: {start_time:.3f}s - {current_time:.3f}s")
            self.app.current_annotation = None
            self.default_labels = {
                "posture": "", "hlb": [], "pa_type": "",
                "behavioral_params": [], "exp_situation": "", "special_notes": ""
            }
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
                print(f"Updated labels for annotation: {target_annotation.start_time:.3f}s")
                self.app.updateAnnotationTimeline()
            else:
                self.default_labels.update(label_data)
                print("Updated default labels for next annotation.")

    @autosave
    def cancelAnnotation(self):
        if self.app.current_annotation is not None:
            print("Canceled annotation creation.")
            self.app.current_annotation = None
            self.default_labels = {
                "posture": "", "hlb": [], "pa_type": "",
                "behavioral_params": [], "exp_situation": "", "special_notes": ""
            }
            self.app.updateAnnotationTimeline() 

    @autosave
    def deleteCurrentLabel(self):
        """Delete the annotation segment at the current timeline position."""
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
        sorted_annotations = sorted(self.app.annotations, key=lambda x: x.start_time)
        current_time = self.app.media_player['_position'] / 1000.0
        target_time = -1 
        current_idx = self.get_current_annotation_index(sorted_annotations)

        if current_idx > 0:
            target_time = sorted_annotations[current_idx - 1].end_time
        elif current_idx == 0:
             target_time = 0
             print("At first label, moving to start.")
        else:
            for annotation in reversed(sorted_annotations):
                if annotation.end_time < current_time:
                    target_time = annotation.end_time
                    break

        if target_time != -1:
            self.app.setPosition(int(target_time * 1000))

    def moveToNextLabel(self):
        sorted_annotations = sorted(self.app.annotations, key=lambda x: x.start_time)
        current_time = self.app.media_player['_position'] / 1000.0
        target_time = -1
        current_idx = self.get_current_annotation_index(sorted_annotations)

        if current_idx != -1:
             if current_idx < len(sorted_annotations) - 1:
                 target_time = sorted_annotations[current_idx + 1].start_time
             else:
                  print("At last label.")
                  pass
        else:
            for annotation in sorted_annotations:
                if annotation.start_time > current_time:
                    target_time = annotation.start_time
                    break

        if target_time != -1:
            self.app.setPosition(int(target_time * 1000))

    @autosave
    def mergeWithPrevious(self):
        """Merge the annotation at the current position with the previous one if adjacent."""
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
            for annotation in [current_annotation, prev_annotation]:
                for i in range(len(self.app.annotations)):
                    if self.app.annotations[i].id == annotation.id:
                        print("Removing annotation during merge:", self.app.annotations[i])
                        del self.app.annotations[i]
                        break
        except ValueError:
             print("Error: Could not remove original annotations during merge.")
             return

        self.app.annotations.append(merged_annotation)
        self.app.annotations.sort(key=lambda x: x.start_time)
        print(f"Merged annotations into: {merged_annotation.start_time:.3f}s - {merged_annotation.end_time:.3f}s")
        self.app.updateAnnotationTimeline()

    @autosave
    def mergeWithNext(self):
        """Merge the annotation at the current position with the next one if adjacent."""
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
            for annotation in [current_annotation, next_annotation]:
                for i in range(len(self.app.annotations)):
                    if self.app.annotations[i].id == annotation.id:
                        print("Removing annotation during merge:", self.app.annotations[i])
                        del self.app.annotations[i]
                        break
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