from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QPointF, QRectF
from PyQt6.QtGui import QPainter, QPen, QColor, QLinearGradient
import json

class TimelineWidget(QWidget):
    def __init__(self, parent=None, show_position=False):
        super().__init__(parent)
        self.parent = parent
        self.show_position = show_position
        self.setMinimumHeight(60)
        self.dragging = None  # None, 'start', or 'end'
        self.hover_edge = None
        self.current_mouse_x = 0  # Store current mouse x position
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.setMouseTracking(True)  # Enable mouse tracking for hover effects
        
    def mousePressEvent(self, event):
        if not hasattr(self.parent, 'media_player'):
            return
            
        duration = self.parent.media_player.duration() / 1000 or 1
        x = event.position().x()
        
        # Check if clicking near annotation edges
        for annotation in self.parent.annotations:
            start_x = (annotation.start_time / duration) * self.width()
            end_x = (annotation.end_time / duration) * self.width()
            
            # Check if click is near edges (within 5 pixels)
            if abs(x - start_x) < 5:
                self.dragging = ('start', annotation)
                break
            elif abs(x - end_x) < 5:
                self.dragging = ('end', annotation)
                break
        
    def mouseReleaseEvent(self, event):
        self.dragging = None
        self.update()
        
    def mouseMoveEvent(self, event):
        if not hasattr(self.parent, 'media_player'):
            return
            
        duration = self.parent.media_player.duration() / 1000 or 1
        x = event.position().x()
        
        if self.dragging:
            edge, annotation = self.dragging
            new_time = (x / self.width()) * duration
            
            # Sort annotations for proper overlap checking
            sorted_annotations = sorted(self.parent.annotations, key=lambda x: x.start_time)
            current_index = sorted_annotations.index(annotation)
            
            # Ensure minimum segment length (0.1 seconds)
            if edge == 'start':
                # Check minimum length
                if annotation.end_time - new_time < 0.1:
                    return
                    
                # Check overlap with previous annotation
                if current_index > 0:
                    prev_annotation = sorted_annotations[current_index - 1]
                    if new_time < prev_annotation.end_time + 0.1:
                        new_time = prev_annotation.end_time + 0.1
                        
                annotation.start_time = max(0, new_time)
            else:  # end
                # Check minimum length
                if new_time - annotation.start_time < 0.1:
                    return
                    
                # Check overlap with next annotation
                if current_index < len(sorted_annotations) - 1:
                    next_annotation = sorted_annotations[current_index + 1]
                    if new_time > next_annotation.start_time - 0.1:
                        new_time = next_annotation.start_time - 0.1
                        
                annotation.end_time = min(duration, new_time)
            
            self.update()
        else:
            # Update cursor based on hover position
            old_hover = self.hover_edge
            self.hover_edge = None
            
            for annotation in self.parent.annotations:
                start_x = (annotation.start_time / duration) * self.width()
                end_x = (annotation.end_time / duration) * self.width()
                
                if abs(x - start_x) < 5 or abs(x - end_x) < 5:
                    self.hover_edge = True
                    self.setCursor(Qt.CursorShape.SizeHorCursor)
                    break
            
            if not self.hover_edge:
                self.setCursor(Qt.CursorShape.ArrowCursor)
            
            if old_hover != self.hover_edge:
                self.update()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        if not hasattr(self.parent, 'media_player'):
            return
            
        duration = self.parent.media_player.duration() / 1000 or 1
        
        # Draw timeline background
        painter.setPen(Qt.PenStyle.NoPen)
        if self.show_position:
            # Progress bar style for second timeline
            painter.setBrush(QColor(20, 20, 20))
            painter.drawRect(QRectF(0, 0, self.width(), self.height()))
            
            # Draw progress
            if duration > 0:
                progress_width = (self.parent.media_player.position() / (duration * 1000)) * self.width()
                progress_gradient = QLinearGradient(0, 0, progress_width, 0)
                progress_gradient.setColorAt(0, QColor(60, 60, 60))
                progress_gradient.setColorAt(1, QColor(80, 80, 80))
                painter.setBrush(progress_gradient)
                painter.drawRect(QRectF(0, 0, progress_width, self.height()))
        else:
            # Main timeline style
            painter.setBrush(QColor(20, 20, 20))
            painter.drawRect(QRectF(0, 0, self.width(), self.height()))
            
            # Draw timeline line
            painter.setPen(QPen(QColor(60, 60, 60), 1))
            y_pos = self.height() / 2
            painter.drawLine(QPointF(0, y_pos), QPointF(self.width(), y_pos))
            
            # Draw current position line
            current_pos = (self.parent.media_player.position() / (duration * 1000)) * self.width()
            painter.setPen(QPen(QColor(200, 200, 200), 1))
            painter.drawLine(QPointF(current_pos, 0), QPointF(current_pos, self.height()))
        
        def draw_annotation_block(start_x, end_x, is_current=False, is_dragging=False, is_edge_hover=False):
            # Enforce minimum display width of 5 pixels
            width = max(5, end_x - start_x)
            if end_x - start_x < 5:
                # Center the block around the actual position
                center = (start_x + end_x) / 2
                start_x = center - 2.5  # Half of min width
                end_x = center + 2.5
            
            height = self.height() * 0.4
            y_pos = (self.height() - height) / 2
            
            # Draw annotation block with different colors based on state
            if is_dragging:
                color = QColor(120, 120, 255, 180)  # Brighter blue when dragging
            elif is_current:
                color = QColor(100, 100, 255, 160)
            else:
                color = QColor(100, 100, 255, 140)
            
            # Draw block
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            painter.drawRoundedRect(QRectF(start_x, y_pos, width, height), 4, 4)
            
            # Draw edge indicators when hovering or dragging
            if is_edge_hover or is_dragging:
                edge_color = QColor(255, 255, 255, 200)
                painter.setPen(QPen(edge_color, 2))
                # Draw edge markers
                marker_height = 8
                painter.drawLine(QPointF(start_x, y_pos - marker_height), QPointF(start_x, y_pos))
                painter.drawLine(QPointF(start_x, y_pos + height), QPointF(start_x, y_pos + height + marker_height))
                painter.drawLine(QPointF(end_x, y_pos - marker_height), QPointF(end_x, y_pos))
                painter.drawLine(QPointF(end_x, y_pos + height), QPointF(end_x, y_pos + height + marker_height))
        
        # Draw current annotation start line
        if hasattr(self.parent, 'current_annotation') and self.parent.current_annotation:
            start_x = (self.parent.current_annotation.start_time / duration) * self.width()
            # Draw green line at start point
            painter.setPen(QPen(QColor(0, 255, 0), 2))  # 2px wide green line
            painter.drawLine(QPointF(start_x, 0), QPointF(start_x, self.height()))

        if hasattr(self.parent, 'annotations'):
            for annotation in self.parent.annotations:
                start_x = (annotation.start_time / duration) * self.width()
                end_x = (annotation.end_time / duration) * self.width()
                width = end_x - start_x
                
                # Store current mouse position during mouseMoveEvent
                mouse_x = self.mapFromGlobal(self.cursor().pos()).x()
                
                # Determine if this annotation is being dragged or hovered
                is_dragging = self.dragging and self.dragging[1] == annotation
                is_edge_hover = (
                    not self.dragging and 
                    self.hover_edge and 
                    (abs(mouse_x - start_x) < 5 or abs(mouse_x - end_x) < 5)
                )
                
                # Draw annotation block with visual feedback
                draw_annotation_block(
                    start_x, 
                    end_x, 
                    is_current=False,
                    is_dragging=is_dragging,
                    is_edge_hover=is_edge_hover
                )
                
                # Draw annotation text if enough space
                if width > 50:
                    painter.setPen(QPen(QColor(255, 255, 255)))
                    try:
                        comment_data = json.loads(annotation.comments[0]["body"])
                        posture = next((item["selectedValue"] for item in comment_data if item["category"] == "POSTURE"), "")
                        hlb = next((item["selectedValue"] for item in comment_data if item["category"] == "HIGH LEVEL BEHAVIOR"), [])
                        
                        if isinstance(hlb, list):
                            text = ", ".join(hlb[:2])
                            if len(hlb) > 2:
                                text += "..."
                        else:
                            text = str(hlb)
                        
                        # Draw combined text
                        text = f"{posture} - {text}"
                        block_height = self.height() * 0.4
                        block_y_pos = (self.height() - block_height) / 2
                        text_rect = QRectF(start_x + 4, block_y_pos, width - 8, block_height)
                        painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, text)
                    except Exception as e:
                        print(f"Error displaying annotation text: {str(e)}")
