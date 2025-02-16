from PyQt6.QtWidgets import QMessageBox
from dialogs import AnnotationDialog
from models import TimelineAnnotation

class AnnotationManager:
    def __init__(self, app):
        self.app = app
        self.default_labels = {
            "posture": "",
            "hlb": [],
            "pa_type": "",
            "behavioral_params": [],
            "exp_situation": "",
            "special_notes": ""
        }
        self.posture_colors = {}  # Store posture-to-color mapping
        
    def get_posture_color(self, posture):
        """Get a consistent color for a given posture"""
        if posture not in self.posture_colors:
            # Generate a new random color for this posture
            import random
            while True:
                # Generate vibrant colors by using higher ranges
                r = random.randint(100, 255)
                g = random.randint(100, 255)
                b = random.randint(100, 255)
                color = f"#{r:02x}{g:02x}{b:02x}"
                # Ensure we don't accidentally reuse a color
                if color not in self.posture_colors.values():
                    break
            self.posture_colors[posture] = color
        return self.posture_colors[posture]
        
    def check_overlap(self, start_time, end_time, exclude_annotation=None):
        """Check if a time range overlaps with any existing annotations"""
        sorted_annotations = sorted(self.app.annotations, key=lambda x: x.start_time)
        for annotation in sorted_annotations:
            if annotation == exclude_annotation:
                continue
            if (start_time <= annotation.end_time and end_time >= annotation.start_time):
                return True
        return False

    def get_current_annotation_index(self, sorted_annotations=None):
        """Get the index of the annotation at current timeline position"""
        current_time = self.app.media_player.position() / 1000
        if sorted_annotations is None:
            sorted_annotations = sorted(self.app.annotations, key=lambda x: x.start_time)
        
        for i, annotation in enumerate(sorted_annotations):
            if annotation.start_time <= current_time <= annotation.end_time:
                return i
        return -1

    def toggleAnnotation(self):
        """Start or finish an annotation at current timeline position"""
        current_time = self.app.media_player.position() / 1000  # Convert ms to seconds
        sorted_annotations = sorted(self.app.annotations, key=lambda x: x.start_time)
        
        if self.app.current_annotation is None:
            # Starting a new annotation
            if self.check_overlap(current_time, current_time):
                return
            self.app.current_annotation = TimelineAnnotation(start_time=current_time)
            # Apply default labels if they exist
            if any(v for v in self.default_labels.values()):
                self.app.current_annotation.update_comment_body(
                    posture=self.default_labels["posture"],
                    hlb=self.default_labels["hlb"],
                    pa_type=self.default_labels["pa_type"],
                    behavioral_params=self.default_labels["behavioral_params"],
                    exp_situation=self.default_labels["exp_situation"],
                    special_notes=self.default_labels["special_notes"]
                )
            # Update timeline position to sync both timelines
            self.app.setPosition(self.app.media_player.position())
        else:
            # Finishing an annotation
            if current_time < self.app.current_annotation.start_time:
                # Don't allow end time before start time
                QMessageBox.warning(self.app, "Invalid Annotation", "End time cannot be before start time.")
                self.app.current_annotation = None
                self.app.updateAnnotationTimeline()
                return
            if self.check_overlap(self.app.current_annotation.start_time, current_time):
                # Don't allow overlapping with existing annotations
                QMessageBox.warning(self.app, "Invalid Annotation", "Annotations cannot overlap with each other.")
                self.app.current_annotation = None
                self.app.updateAnnotationTimeline()
                return
            
            # Add the annotation and maintain order
            self.app.current_annotation.end_time = current_time
            self.app.annotations.append(self.app.current_annotation)
            self.app.annotations.sort(key=lambda x: x.start_time)
            self.app.current_annotation = None
            self.app.updateAnnotationTimeline()
            # Update timeline position to sync both timelines
            self.app.setPosition(self.app.media_player.position())
            
    def editAnnotation(self):
        """Edit the annotation at current timeline position or pre-set labels for next annotation"""
        sorted_annotations = sorted(self.app.annotations, key=lambda x: x.start_time)
        current_idx = self.get_current_annotation_index(sorted_annotations)
        
        # Create dialog with existing annotation or None for new labels
        annotation = sorted_annotations[current_idx] if current_idx != -1 else None
        dialog = AnnotationDialog(annotation, self.app)
        if dialog.exec():
            posture = next(item.text() for item in dialog.posture_list.selectedItems())
            hlb = [item.text() for item in dialog.hlb_list.selectedItems()]
            pa_type = next(item.text() for item in dialog.pa_list.selectedItems())
            behavioral_params = [item.text() for item in dialog.bp_list.selectedItems()]
            exp_situation = next(item.text() for item in dialog.es_list.selectedItems())
            special_notes = dialog.notes_edit.text()
            
            if annotation:
                # Update existing annotation
                annotation.update_comment_body(
                    posture=posture,
                    hlb=hlb,
                    pa_type=pa_type,
                    behavioral_params=behavioral_params,
                    exp_situation=exp_situation,
                    special_notes=special_notes
                )
            else:
                # Store as default values for next annotation
                self.default_labels.update({
                    "posture": posture,
                    "hlb": hlb,
                    "pa_type": pa_type,
                    "behavioral_params": behavioral_params,
                    "exp_situation": exp_situation,
                    "special_notes": special_notes
                })

    def cancelAnnotation(self):
        """Cancel the current annotation in progress"""
        if self.app.current_annotation is not None:
            self.app.current_annotation = None
            self.app.updateAnnotationTimeline()

    def deleteCurrentLabel(self):
        """Delete the label at current timeline position"""
        sorted_annotations = sorted(self.app.annotations, key=lambda x: x.start_time)
        current_idx = self.get_current_annotation_index(sorted_annotations)
        
        if current_idx != -1:
            # Delete the current annotation
            self.app.annotations.remove(sorted_annotations[current_idx])
            self.app.updateAnnotationTimeline()
        else:
            # If no annotation at current time, delete the last annotation that ends before current time
            current_time = self.app.media_player.position() / 1000
            for annotation in reversed(sorted_annotations):
                if annotation.end_time < current_time:
                    self.app.annotations.remove(annotation)
                    self.app.updateAnnotationTimeline()
                    break

    def moveToPreviousLabel(self):
        """Move to the end of the previous label"""
        sorted_annotations = sorted(self.app.annotations, key=lambda x: x.start_time)
        current_time = self.app.media_player.position() / 1000
        current_idx = self.get_current_annotation_index(sorted_annotations)
        
        # If we're in an annotation, look before current_idx
        # Otherwise find the last annotation before current_time
        if current_idx != -1:
            if current_idx > 0:
                prev_annotation = sorted_annotations[current_idx - 1]
                self.app.media_player.setPosition(int(prev_annotation.end_time * 1000))
        else:
            # Find the last annotation that ends before current_time
            for annotation in reversed(sorted_annotations):
                if annotation.end_time < current_time:
                    self.app.media_player.setPosition(int(annotation.end_time * 1000))
                    break

    def moveToNextLabel(self):
        """Move to the start of the next label"""
        sorted_annotations = sorted(self.app.annotations, key=lambda x: x.start_time)
        current_time = self.app.media_player.position() / 1000
        current_idx = self.get_current_annotation_index(sorted_annotations)
        
        # If we're in an annotation, look after current_idx
        # Otherwise find the first annotation after current_time
        if current_idx != -1:
            if current_idx < len(sorted_annotations) - 1:
                next_annotation = sorted_annotations[current_idx + 1]
                self.app.media_player.setPosition(int(next_annotation.start_time * 1000))
        else:
            # Find the first annotation that starts after current_time
            for annotation in sorted_annotations:
                if annotation.start_time > current_time:
                    self.app.media_player.setPosition(int(annotation.start_time * 1000))
                    break

    def mergeWithPrevious(self):
        """Merge current label with the previous label"""
        sorted_annotations = sorted(self.app.annotations, key=lambda x: x.start_time)
        current_idx = self.get_current_annotation_index(sorted_annotations)
        
        if current_idx > 0:
            current_annotation = sorted_annotations[current_idx]
            prev_annotation = sorted_annotations[current_idx - 1]            
            # Check if annotations are adjacent (within small threshold or exactly at boundary)
            gap = abs(prev_annotation.end_time - current_annotation.start_time)
            if gap > 0.001:  # Use a smaller threshold to handle floating point precision
                QMessageBox.warning(self.app, "Invalid Merge", "Can only merge adjacent annotations.")
                return
            
            # Remove original annotations first
            del self.app.annotations[current_idx]
            del self.app.annotations[current_idx - 1]
        

            # Create the merged annotation
            merged_annotation = TimelineAnnotation(
                start_time=prev_annotation.start_time,
                end_time=current_annotation.end_time
            )
            
            # Copy comments from previous annotation if it has them
            if prev_annotation.comments:
                merged_annotation.copy_comments_from(prev_annotation)
            # Otherwise copy from current annotation if it has comments
            elif current_annotation.comments:
                merged_annotation.copy_comments_from(current_annotation)
            
            # Add the merged annotation
            self.app.annotations.append(merged_annotation)
            
            # Sort annotations to maintain order
            self.app.annotations.sort(key=lambda x: x.start_time)
            
            # Update timeline
            self.app.updateAnnotationTimeline()

            self.app.timeline_widget.update()
            
            # Update position to trigger timeline sync
            self.app.setPosition(self.app.media_player.position())

    def mergeWithNext(self):
        """Merge current label with the next label"""
        sorted_annotations = sorted(self.app.annotations, key=lambda x: x.start_time)
        current_idx = self.get_current_annotation_index(sorted_annotations)
        
        if current_idx != -1 and current_idx < len(sorted_annotations) - 1:
            current_annotation = sorted_annotations[current_idx]
            next_annotation = sorted_annotations[current_idx + 1]
            
            # Check if annotations are adjacent (within small threshold or exactly at boundary)
            gap = abs(current_annotation.end_time - next_annotation.start_time)
            if gap > 0.001:  # Use a smaller threshold to handle floating point precision
                QMessageBox.warning(self.app, "Invalid Merge", "Can only merge adjacent annotations.")
                return
            
            # Create the merged annotation before removing the originals
            merged_annotation = TimelineAnnotation(
                start_time=current_annotation.start_time,
                end_time=next_annotation.end_time
            )
            
            # Copy comments from current annotation if it has them
            if current_annotation.comments:
                merged_annotation.copy_comments_from(current_annotation)
            # Otherwise copy from next annotation if it has comments
            elif next_annotation.comments:
                merged_annotation.copy_comments_from(next_annotation)
            
            # First add the merged annotation
            self.app.annotations.append(merged_annotation)
            
            # Then remove the original annotations
            # Remove in reverse order (next then current) to maintain correct indices
            del self.app.annotations[current_idx + 1]
            del self.app.annotations[current_idx]
            
            # Sort annotations to maintain order
            self.app.annotations.sort(key=lambda x: x.start_time)
            
            # Update timeline
            self.app.updateAnnotationTimeline()
            
            # Update position to trigger timeline sync
            self.app.setPosition(self.app.media_player.position())

    def splitCurrentLabel(self):
        """Split the current label at the current position"""
        current_time = self.app.media_player.position() / 1000
        sorted_annotations = sorted(self.app.annotations, key=lambda x: x.start_time)
        current_idx = self.get_current_annotation_index(sorted_annotations)
        
        if current_idx != -1:
            annotation = sorted_annotations[current_idx]
            # Only split if we're not at the boundaries
            if annotation.start_time < current_time < annotation.end_time:
                # Ensure minimum segment length (0.1 seconds)
                if current_time - annotation.start_time < 0.1 or annotation.end_time - current_time < 0.1:
                    QMessageBox.warning(self.app, "Invalid Split", "Split point too close to segment boundary.")
                    return
                
                # Create new annotation for the second half
                new_annotation = TimelineAnnotation(
                    start_time=current_time,
                    end_time=annotation.end_time
                )
                
                # Copy annotation data including comments
                new_annotation.copy_comments_from(annotation)
                
                # Update the end time of the current annotation
                annotation.end_time = current_time
                
                # Add the new annotation and resort
                self.app.annotations.append(new_annotation)
                self.app.annotations.sort(key=lambda x: x.start_time)
                self.app.updateAnnotationTimeline()
