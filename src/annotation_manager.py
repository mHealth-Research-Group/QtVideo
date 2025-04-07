from PyQt6.QtWidgets import QMessageBox
from src.dialogs import AnnotationDialog
from src.models import TimelineAnnotation

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
        self.posture_colors = {}
        
    def get_posture_color(self, posture):
        """Get a consistent color for a given posture"""
        if posture not in self.posture_colors:
            import random
            while True:
                r = random.randint(100, 255)
                g = random.randint(100, 255)
                b = random.randint(100, 255)
                color = f"#{r:02x}{g:02x}{b:02x}"
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
            if self.check_overlap(current_time, current_time):
                return
            self.app.current_annotation = TimelineAnnotation(start_time=current_time)
            self.app.current_annotation.update_comment_body(
                posture=self.default_labels.get("posture", ""),
                hlb=self.default_labels.get("hlb", []),
                pa_type=self.default_labels.get("pa_type", ""),
                behavioral_params=self.default_labels.get("behavioral_params", []),
                exp_situation=self.default_labels.get("exp_situation", ""),
                special_notes=self.default_labels.get("special_notes", "")
            )
            self.app.setPosition(self.app.media_player.position())
        else:
            if current_time < self.app.current_annotation.start_time:
                QMessageBox.warning(self.app, "Invalid Annotation", "End time cannot be before start time.")
                self.app.current_annotation = None
                self.app.updateAnnotationTimeline()
                return
            if self.check_overlap(self.app.current_annotation.start_time, current_time):
                QMessageBox.warning(self.app, "Invalid Annotation", "Annotations cannot overlap with each other.")
                self.app.current_annotation = None
                self.app.updateAnnotationTimeline()
                return
            
            self.app.current_annotation.end_time = current_time
            self.app.annotations.append(self.app.current_annotation)
            self.app.annotations.sort(key=lambda x: x.start_time)
            self.app.current_annotation = None
            self.default_labels = {
                "posture": "",
                "hlb": [],
                "pa_type": "",
                "behavioral_params": [],
                "exp_situation": "",
                "special_notes": ""
            }
            self.app.updateAnnotationTimeline()
            self.app.setPosition(self.app.media_player.position())
            
    def editAnnotation(self):
        """Edit the annotation at current timeline position or pre-set labels for next annotation"""
        sorted_annotations = sorted(self.app.annotations, key=lambda x: x.start_time)
        current_idx = self.get_current_annotation_index(sorted_annotations)
        
        annotation = sorted_annotations[current_idx] if current_idx != -1 else None
        dialog = AnnotationDialog(annotation, self.app)
        if dialog.exec():
            posture = next(item.text() for item in dialog.posture_list.selectedItems())
            hlb = [item.text() for item in dialog.hlb_list.selectedItems()]
            pa_type = next(item.text() for item in dialog.pa_list.selectedItems())
            behavioral_params = [item.text() for item in dialog.bp_list.selectedItems()]
            exp_situation = next(item.text() for item in dialog.es_list.selectedItems())
            special_notes = dialog.notes_edit.text()
            
            label_data = {
                "posture": posture,
                "hlb": hlb,
                "pa_type": pa_type,
                "behavioral_params": behavioral_params,
                "exp_situation": exp_situation,
                "special_notes": special_notes
            }

            if annotation:
                annotation.update_comment_body(**label_data)
            else:
                if self.app.current_annotation:
                    self.app.current_annotation.update_comment_body(**label_data)
                self.default_labels.update(label_data)

    def cancelAnnotation(self):
        """Cancel the current annotation in progress"""
        if self.app.current_annotation is not None:
            self.app.current_annotation = None
            self.default_labels = {
                "posture": "",
                "hlb": [],
                "pa_type": "",
                "behavioral_params": [],
                "exp_situation": "",
                "special_notes": ""
            }
            self.app.updateAnnotationTimeline()

    def deleteCurrentLabel(self):
        """Delete the label at current timeline position"""
        sorted_annotations = sorted(self.app.annotations, key=lambda x: x.start_time)
        current_idx = self.get_current_annotation_index(sorted_annotations)
        
        if current_idx != -1:
            self.app.annotations.remove(sorted_annotations[current_idx])
            self.app.updateAnnotationTimeline()
        else:
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
            # Check if annotations are adjacent 
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
            elif current_annotation.comments:
                merged_annotation.copy_comments_from(current_annotation)
            
            # Add the merged annotation
            self.app.annotations.append(merged_annotation)
            
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
            gap = abs(current_annotation.end_time - next_annotation.start_time)
            if gap > 0.001:
                QMessageBox.warning(self.app, "Invalid Merge", "Can only merge adjacent annotations.")
                return
            
            merged_annotation = TimelineAnnotation(
                start_time=current_annotation.start_time,
                end_time=next_annotation.end_time
            )
            
            if current_annotation.comments:
                merged_annotation.copy_comments_from(current_annotation)
            elif next_annotation.comments:
                merged_annotation.copy_comments_from(next_annotation)
        
            self.app.annotations.append(merged_annotation)
            
            del self.app.annotations[current_idx + 1]
            del self.app.annotations[current_idx]
            
            self.app.annotations.sort(key=lambda x: x.start_time)
            
            self.app.updateAnnotationTimeline()
            
            self.app.setPosition(self.app.media_player.position())

    def splitCurrentLabel(self):
        """Split the current label at the current position"""
        current_time = self.app.media_player.position() / 1000
        sorted_annotations = sorted(self.app.annotations, key=lambda x: x.start_time)
        current_idx = self.get_current_annotation_index(sorted_annotations)
        
        if current_idx != -1:
            annotation = sorted_annotations[current_idx]
            if annotation.start_time < current_time < annotation.end_time:
                if current_time - annotation.start_time < 0.1 or annotation.end_time - current_time < 0.1:
                    QMessageBox.warning(self.app, "Invalid Split", "Split point too close to segment boundary.")
                    return

                new_annotation = TimelineAnnotation(
                    start_time=current_time,
                    end_time=annotation.end_time
                )
                
                new_annotation.copy_comments_from(annotation)
                
                annotation.end_time = current_time
                
                self.app.annotations.append(new_annotation)
                self.app.annotations.sort(key=lambda x: x.start_time)
                self.app.updateAnnotationTimeline()
