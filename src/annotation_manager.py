# src/annotation_manager.py

from PySide6.QtWidgets import QMessageBox
from src.dialogs import AnnotationDialog
from src.models import TimelineAnnotation
import random
from src.utils import autosave

class AnnotationManager:
    def __init__(self, app):
        self.app = app
        # Default values for new annotations or when dialog is used without a current selection
        self.default_labels = {
            "posture": "",
            "hlb": [],
            "pa_type": "",
            "behavioral_params": [],
            "exp_situation": "",
            "special_notes": ""
        }
        self.posture_colors = {} # Cache for consistent posture colors

    def get_posture_color(self, posture):
        """Get a consistent color for a given posture, generating one if needed."""
        if posture is None or posture == "": # Handle empty/None posture
             return "#808080" # Default grey for undefined posture

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
        """Check if a given time range overlaps with existing annotations, excluding one."""
        # Use a small tolerance to avoid issues with floating point precision at boundaries
        tolerance = 0.001
        for annotation in self.app.annotations:
            if annotation == exclude_annotation:
                continue
            # Overlap condition: (StartA < EndB) and (EndA > StartB)
            if (start_time < (annotation.end_time - tolerance) and
                    end_time > (annotation.start_time + tolerance)):
                return True
        return False

    def get_current_annotation_index(self, sorted_annotations=None):
        """Get the index of the annotation at the current timeline position."""
        # Convert position from ms to seconds
        current_time = self.app.media_player['_position'] / 1000.0
        if sorted_annotations is None:
            # Ensure annotations are sorted by start time
            sorted_annotations = sorted(self.app.annotations, key=lambda x: x.start_time)

        for i, annotation in enumerate(sorted_annotations):
            tolerance = 0.001
            if (annotation.start_time - tolerance) <= current_time <= (annotation.end_time + tolerance):
                return i
            else:
                print(f"Current time {current_time:.3f}s is NOT inside annotation {i}: {annotation.start_time:.3f}s - {annotation.end_time:.3f}s")
        return -1 # Return -1 if no annotation contains the current time

    @autosave
    def toggleAnnotation(self):
        """Start or finish an annotation at the current timeline position."""
        current_time = self.app.media_player['_position'] / 1000.0 # Position in seconds

        if self.app.current_annotation is None:
            # --- Start a new annotation ---
            # Check if the starting point falls within any existing annotation
            if self.check_overlap(current_time, current_time):
                QMessageBox.warning(self.app, "Overlap Detected",
                                    "Cannot start an annotation within an existing one.")
                return

            # Create a new annotation instance starting at the current time
            self.app.current_annotation = TimelineAnnotation(start_time=current_time)
            # Pre-fill with default labels (or labels set via dialog)
            self.app.current_annotation.update_comment_body(**self.default_labels)
            print(f"Started annotation at {current_time:.3f}s")
            # No need to call setPosition, just update the visual timeline
            self.app.updateAnnotationTimeline()

        else:
            # --- Finish the current annotation ---
            start_time = self.app.current_annotation.start_time

            # Basic validation: end time must be after start time
            if current_time <= start_time:
                QMessageBox.warning(self.app, "Invalid End Time",
                                    "End time must be after the start time.")
                return

            if self.check_overlap(start_time, current_time, exclude_annotation=self.app.current_annotation):
                QMessageBox.warning(self.app, "Overlap Detected",
                                    "Annotations cannot overlap.")
                return

            # Finalize the annotation
            self.app.current_annotation.end_time = current_time
            self.app.annotations.append(self.app.current_annotation)
            self.app.annotations.sort(key=lambda x: x.start_time) # Keep the list sorted
            print(f"Finished annotation: {start_time:.3f}s - {current_time:.3f}s")

            # Clear the temporary annotation object
            self.app.current_annotation = None

            # Reset default labels for the next potential annotation
            self.default_labels = {
                "posture": "", "hlb": [], "pa_type": "",
                "behavioral_params": [], "exp_situation": "", "special_notes": ""
            }

            # Update the timeline display
            self.app.updateAnnotationTimeline()

    @autosave
    def editAnnotation(self):
        """Edit labels of the annotation at the current position, or set defaults for the next."""
        sorted_annotations = sorted(self.app.annotations, key=lambda x: x.start_time)
        current_idx = self.get_current_annotation_index(sorted_annotations)

        target_annotation = None
        if current_idx != -1:
            # If playhead is inside an existing annotation, target it
            target_annotation = sorted_annotations[current_idx]
        elif self.app.current_annotation:
            # If an annotation is currently being created, target it
            target_annotation = self.app.current_annotation

        # Pass the target annotation (or None) to the dialog
        dialog = AnnotationDialog(target_annotation, self.app)

        if dialog.exec():
            posture_items = dialog.posture_list.selectedItems()
            posture = posture_items[0].text() if posture_items else ""

            hlb_items = dialog.hlb_list.selectedItems()
            hlb = [item.text() for item in hlb_items]

            pa_type_items = dialog.pa_list.selectedItems()
            pa_type = pa_type_items[0].text() if pa_type_items else ""

            bp_items = dialog.bp_list.selectedItems()
            behavioral_params = [item.text() for item in bp_items]

            es_items = dialog.es_list.selectedItems()
            exp_situation = es_items[0].text() if es_items else ""

            special_notes = dialog.notes_edit.text()

            # Prepare data dictionary
            label_data = {
                "posture": posture, "hlb": hlb, "pa_type": pa_type,
                "behavioral_params": behavioral_params, "exp_situation": exp_situation,
                "special_notes": special_notes
            }

            if target_annotation:
                # If we targeted an existing or currently-being-created annotation, update it
                target_annotation.update_comment_body(**label_data)
                print(f"Updated labels for annotation: {target_annotation.start_time:.3f}s")
                # Need to update timeline if comments affect display (like color)
                self.app.updateAnnotationTimeline()
            else:
                # If no annotation was targeted, update the default labels for the next one
                self.default_labels.update(label_data)
                print("Updated default labels for next annotation.")


    @autosave
    def cancelAnnotation(self):
        """Cancel the creation of the current annotation (if one is being created)."""
        if self.app.current_annotation is not None:
            print("Canceled annotation creation.")
            self.app.current_annotation = None
            # Reset default labels as well
            self.default_labels = {
                "posture": "", "hlb": [], "pa_type": "",
                "behavioral_params": [], "exp_situation": "", "special_notes": ""
            }
            self.app.updateAnnotationTimeline() 

    @autosave
    def deleteCurrentLabel(self):
        """Delete the annotation segment at the current timeline position."""
        # Ensure annotations are sorted before getting index
        sorted_annotations = sorted(self.app.annotations, key=lambda x: x.start_time)
        current_idx = self.get_current_annotation_index(sorted_annotations)

        if current_idx != -1:
            annotation_to_delete = sorted_annotations[current_idx]
            confirm = QMessageBox.question(self.app, "Confirm Delete",
                                           f"Delete annotation from {annotation_to_delete.start_time:.2f}s to {annotation_to_delete.end_time:.2f}s?",
                                           QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                           QMessageBox.StandardButton.No)

            if confirm == QMessageBox.StandardButton.Yes:
                # Remove the annotation by object reference from the main list
                try:
                    del self.app.annotations[current_idx]
                    self.app.updateAnnotationTimeline()
                except ValueError:
                     print("Error: Annotation to delete not found in main list.") # Should not happen if logic is correct
        else:
             # If playhead is not inside any annotation, do nothing or show a message
             print("Delete action: Playhead is not inside any annotation.")
             QMessageBox.information(self.app, "Delete Label", "The playback position is not currently inside any annotation.")


    def moveToPreviousLabel(self):
        """Move the playhead to the end time of the previous annotation segment."""
        sorted_annotations = sorted(self.app.annotations, key=lambda x: x.start_time)
        current_time = self.app.media_player['_position'] / 1000.0
        target_time = -1 # Initialize target time

        # Find the index of the annotation *containing* current_time
        current_idx = self.get_current_annotation_index(sorted_annotations)

        if current_idx > 0:
            # If inside an annotation (and not the first), target the end of the one before it
            target_time = sorted_annotations[current_idx - 1].end_time
        elif current_idx == 0:
             # If inside the first annotation, maybe go to start of video or do nothing?
             target_time = 0 # Go to start
             print("At first label, moving to start.")
        else:
            # If not inside any annotation, find the last one that *ends* before current_time
            for annotation in reversed(sorted_annotations):
                if annotation.end_time < current_time:
                    target_time = annotation.end_time
                    break

        if target_time != -1:
            # Move playhead (convert seconds back to ms)
            self.app.setPosition(int(target_time * 1000))

    def moveToNextLabel(self):
        """Move the playhead to the start time of the next annotation segment."""
        sorted_annotations = sorted(self.app.annotations, key=lambda x: x.start_time)
        current_time = self.app.media_player['_position'] / 1000.0
        target_time = -1

        # Find the index of the annotation *containing* current_time
        current_idx = self.get_current_annotation_index(sorted_annotations)

        if current_idx != -1:
             # If inside an annotation, find the next one
             if current_idx < len(sorted_annotations) - 1:
                 target_time = sorted_annotations[current_idx + 1].start_time
             else:
                  # Inside the last annotation, maybe go to end or do nothing?
                  print("At last label.")
                  pass
        else:
            # If not inside any annotation, find the first one that *starts* after current_time
            for annotation in sorted_annotations:
                if annotation.start_time > current_time:
                    target_time = annotation.start_time
                    break

    @autosave
        if target_time != -1:
            self.app.setPosition(int(target_time * 1000))


    def mergeWithPrevious(self):
        """Merge the annotation at the current position with the previous one if adjacent."""
        sorted_annotations = sorted(self.app.annotations, key=lambda x: x.start_time)
        current_idx = self.get_current_annotation_index(sorted_annotations)

        if current_idx is None or current_idx <= 0:
            QMessageBox.information(self.app, "Merge Failed", "Cannot merge: No annotation at current position or no previous annotation exists.")
            return

        current_annotation = sorted_annotations[current_idx]
        prev_annotation = sorted_annotations[current_idx - 1]

        # Check for adjacency (allow small gap/overlap due to float precision)
        gap = current_annotation.start_time - prev_annotation.end_time
        if abs(gap) > 0.01: # Check if gap is larger than 10ms
            QMessageBox.warning(self.app, "Invalid Merge", f"Cannot merge: Annotations are not adjacent (Gap: {gap:.3f}s).")
            return

        # Create the merged annotation
        merged_annotation = TimelineAnnotation(
            start_time=prev_annotation.start_time,
            end_time=current_annotation.end_time
        )

        # Copy comments: prioritize the annotation the user was "in" (current), then previous.
        if current_annotation.comments:
            merged_annotation.copy_comments_from(current_annotation)
        elif prev_annotation.comments:
            merged_annotation.copy_comments_from(prev_annotation)
        else:
             # If neither have comments, initialize with defaults (optional)
             merged_annotation.update_comment_body(**self.default_labels)

        # Remove original annotations by object reference
        try:
            self.app.annotations.remove(current_annotation)
            self.app.annotations.remove(prev_annotation)
        except ValueError:
             print("Error: Could not remove original annotations during merge.")
             return

        # Add the merged annotation
        self.app.annotations.append(merged_annotation)
        self.app.annotations.sort(key=lambda x: x.start_time) # Re-sort

        print(f"Merged annotations into: {merged_annotation.start_time:.3f}s - {merged_annotation.end_time:.3f}s")

        # Update timeline display
        self.app.updateAnnotationTimeline()
        # No setPosition needed

    def mergeWithNext(self):
        """Merge the annotation at the current position with the next one if adjacent."""
        sorted_annotations = sorted(self.app.annotations, key=lambda x: x.start_time)
        current_idx = self.get_current_annotation_index(sorted_annotations)

        if current_idx == -1 or current_idx >= len(sorted_annotations) - 1:
            QMessageBox.information(self.app, "Merge Failed", "Cannot merge: No annotation at current position or no next annotation exists.")
            return

        current_annotation = sorted_annotations[current_idx]
        next_annotation = sorted_annotations[current_idx + 1]

        # Check for adjacency
        gap = next_annotation.start_time - current_annotation.end_time
        if abs(gap) > 0.01: # Check if gap is larger than 10ms
            QMessageBox.warning(self.app, "Invalid Merge", f"Cannot merge: Annotations are not adjacent (Gap: {gap:.3f}s).")
            return

        # Create the merged annotation
        merged_annotation = TimelineAnnotation(
            start_time=current_annotation.start_time,
            end_time=next_annotation.end_time
        )

        # Copy comments: prioritize the annotation the user was "in" (current), then next.
        if current_annotation.comments:
            merged_annotation.copy_comments_from(current_annotation)
        elif next_annotation.comments:
            merged_annotation.copy_comments_from(next_annotation)
        else:
            merged_annotation.update_comment_body(**self.default_labels)

        # Remove original annotations by object reference
        try:
            self.app.annotations.remove(current_annotation)
            self.app.annotations.remove(next_annotation)
        except ValueError:
             print("Error: Could not remove original annotations during merge.")
             return

        # Add the merged annotation
        self.app.annotations.append(merged_annotation)
        self.app.annotations.sort(key=lambda x: x.start_time) # Re-sort

        print(f"Merged annotations into: {merged_annotation.start_time:.3f}s - {merged_annotation.end_time:.3f}s")

        # Update timeline display
        self.app.updateAnnotationTimeline()

    def splitCurrentLabel(self):
        """Split the annotation at the current playhead position into two."""
        current_time = self.app.media_player['_position'] / 1000.0 # Position in seconds
        sorted_annotations = sorted(self.app.annotations, key=lambda x: x.start_time)
        current_idx = self.get_current_annotation_index(sorted_annotations)

        if current_idx == -1:
            QMessageBox.information(self.app, "Split Failed", "Cannot split: Playhead is not inside an annotation.")
            return

        annotation_to_split = sorted_annotations[current_idx]

        # Check if the split point is valid (not too close to boundaries)
        min_duration = 0.1
        if not (annotation_to_split.start_time < current_time < annotation_to_split.end_time):
             QMessageBox.warning(self.app, "Invalid Split", "Split point must be strictly inside the annotation.")
             return
        if (current_time - annotation_to_split.start_time < min_duration or
                annotation_to_split.end_time - current_time < min_duration):
            QMessageBox.warning(self.app, "Invalid Split", f"Split results in segment smaller than {min_duration}s.")
            return

        # Create the second part of the split annotation
        new_annotation = TimelineAnnotation(
            start_time=current_time,
            end_time=annotation_to_split.end_time
        )
        # Copy comments/labels from the original annotation to the new part
        new_annotation.copy_comments_from(annotation_to_split)

        # Modify the original annotation to be the first part
        original_end_time = annotation_to_split.end_time # Store for logging
        annotation_to_split.end_time = current_time

        # Add the new second part to the list
        self.app.annotations.append(new_annotation)
        self.app.annotations.sort(key=lambda x: x.start_time) # Re-sort

        print(f"Split annotation {annotation_to_split.start_time:.3f}s-{original_end_time:.3f}s at {current_time:.3f}s")

        # Update timeline display
        self.app.updateAnnotationTimeline()