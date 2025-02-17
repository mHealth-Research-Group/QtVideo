from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QPointF, QRectF
from PyQt6.QtGui import QPainter, QPen, QColor, QLinearGradient
import json

class TimelineWidget(QWidget):
    def __init__(self, parent=None, show_position=False, is_main_timeline=True):
        super().__init__(parent)
        self.parent = parent
        self.show_position = show_position
        self.is_main_timeline = is_main_timeline
        self.setMinimumHeight(60)
        self.dragging = None 
        self.hover_edge = None
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.setMouseTracking(True) 
        
    
        
    def mousePressEvent(self, event):
        if not hasattr(self.parent, 'media_player'):
            return
            
        duration = self.parent.media_player.duration() / 1000 or 1
        x = event.position().x()
        width_percent = x / self.width()

        if self.is_main_timeline:
            zoom_start_x = self.parent.zoom_start * self.width()
            zoom_end_x = self.parent.zoom_end * self.width()
            
            if abs(x - zoom_start_x) < 5:
                self.dragging = 'zoom_start'
                return
            elif abs(x - zoom_end_x) < 5:
                self.dragging = 'zoom_end'
                return
        
        # Check if clicking near annotation edges
        for annotation in self.parent.annotations:
            if self.is_main_timeline:
                start_x = (annotation.start_time / duration) * self.width()
                end_x = (annotation.end_time / duration) * self.width()
            else:
                # Adjust coordinates w
                visible_duration = (self.parent.zoom_end - self.parent.zoom_start) * duration
                visible_start = self.parent.zoom_start * duration
                
                if visible_duration > 0:
                    # Convert annotation times to relative positions in zoomed view
                    relative_start = (annotation.start_time - visible_start) / visible_duration
                    relative_end = (annotation.end_time - visible_start) / visible_duration

                    start_x = relative_start * self.width()
                    end_x = relative_end * self.width()
                
                    if end_x < 0 or start_x > self.width():
                        continue
                    
                    start_x = max(0, min(start_x, self.width()))
                    end_x = max(0, min(end_x, self.width()))

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
        
        if not self.dragging:
            return

        if self.dragging in ['zoom_start', 'zoom_end']:
            width_percent = max(0.0, min(1.0, x / self.width()))
            
            if self.dragging == 'zoom_start':
                if width_percent < self.parent.zoom_end - 0.05:
                    self.parent.zoom_start = width_percent
                    self.parent.timeline_widget.update()
                    self.parent.second_timeline_widget.update()
            else:  # zoom_end
                if width_percent > self.parent.zoom_start + 0.05: 
                    self.parent.zoom_end = width_percent
                    self.parent.timeline_widget.update()
                    self.parent.second_timeline_widget.update()
            return
            
        # Handle annotation dragging
        if isinstance(self.dragging, tuple):
            edge, annotation = self.dragging
            if self.is_main_timeline:
                new_time = (x / self.width()) * duration
            else:
                visible_duration = (self.parent.zoom_end - self.parent.zoom_start) * duration
                visible_start = self.parent.zoom_start * duration
                new_time = visible_start + (x / self.width()) * visible_duration
        
            sorted_annotations = sorted(self.parent.annotations, key=lambda x: x.start_time)
            current_index = sorted_annotations.index(annotation)
            
            if edge == 'start':
                if annotation.end_time - new_time < 0.1:
                    return

                if current_index > 0:
                    prev_annotation = sorted_annotations[current_index - 1]
                    if new_time < prev_annotation.end_time + 0.1:
                        new_time = prev_annotation.end_time + 0.1
                        
                annotation.start_time = max(0, new_time)
            else: 
                if new_time - annotation.start_time < 0.1:
                    return
                    
                if current_index < len(sorted_annotations) - 1:
                    next_annotation = sorted_annotations[current_index + 1]
                    if new_time > next_annotation.start_time - 0.1:
                        new_time = next_annotation.start_time - 0.1
                        
                annotation.end_time = min(duration, new_time)
            
            self.parent.timeline_widget.update()
            self.parent.second_timeline_widget.update()
        else:
            old_hover = self.hover_edge
            self.hover_edge = None
            
            for annotation in self.parent.annotations:
                if self.is_main_timeline:
                    start_x = (annotation.start_time / duration) * self.width()
                    end_x = (annotation.end_time / duration) * self.width()
                else:
                    # Adjust coordinates for zoomed view
                    visible_duration = (self.parent.zoom_end - self.parent.zoom_start) * duration
                    visible_start = self.parent.zoom_start * duration
                    
                    if visible_duration > 0:
                        relative_start = (annotation.start_time - visible_start) / visible_duration
                        relative_end = (annotation.end_time - visible_start) / visible_duration
                        
                        start_x = relative_start * self.width()
                        end_x = relative_end * self.width()
                        

                        if end_x < 0 or start_x > self.width():
                            continue

                        start_x = max(0, min(start_x, self.width()))
                        end_x = max(0, min(end_x, self.width()))
                
                if abs(x - start_x) < 5:
                    self.hover_edge = ('start', annotation)
                    self.setCursor(Qt.CursorShape.SizeHorCursor)
                    break
                elif abs(x - end_x) < 5:
                    self.hover_edge = ('end', annotation)
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

        if not self.is_main_timeline:
            visible_duration = (self.parent.zoom_end - self.parent.zoom_start) * duration
            visible_start = self.parent.zoom_start * duration
        
        painter.setPen(Qt.PenStyle.NoPen)
        if self.show_position:
            painter.setBrush(QColor(20, 20, 20))
            painter.drawRect(QRectF(0, 0, self.width(), self.height()))
            
            if duration > 0:
                if self.is_main_timeline:
                    progress_width = (self.parent.media_player.position() / (duration * 1000)) * self.width()
                else:
    
                    position = self.parent.media_player.position() / 1000  # Convert to seconds
                    if visible_duration > 0:  # Prevent division by zero
                        relative_pos = (position - visible_start) / visible_duration
                        progress_width = relative_pos * self.width()
                        if 0 <= progress_width <= self.width():  # Only draw if within bounds
                            progress_gradient = QLinearGradient(0, 0, progress_width, 0)
                            progress_gradient.setColorAt(0, QColor(60, 60, 60))
                            progress_gradient.setColorAt(1, QColor(80, 80, 80))
                            painter.setBrush(progress_gradient)
                            painter.drawRect(QRectF(0, 0, progress_width, self.height()))
        else:
            # Main timeline style
            painter.setBrush(QColor(20, 20, 20))
            painter.drawRect(QRectF(0, 0, self.width(), self.height()))
            
            painter.setPen(QPen(QColor(60, 60, 60), 1))
            y_pos = self.height() / 2
            painter.drawLine(QPointF(0, y_pos), QPointF(self.width(), y_pos))
            if self.is_main_timeline:
                current_pos = (self.parent.media_player.position() / (duration * 1000)) * self.width()
            else:
                position = self.parent.media_player.position() / 1000
                relative_pos = (position - visible_start) / visible_duration
                current_pos = relative_pos * self.width()
                
            painter.setPen(QPen(QColor(200, 200, 200), 1))
            if 0 <= current_pos <= self.width():
                painter.drawLine(QPointF(current_pos, 0), QPointF(current_pos, self.height()))

            if self.is_main_timeline:
                zoom_start_x = self.parent.zoom_start * self.width()
                zoom_end_x = self.parent.zoom_end * self.width()
            
                painter.setPen(QPen(QColor(255, 0, 0), 2))
                painter.drawLine(QPointF(zoom_start_x, 0), QPointF(zoom_start_x, self.height()))
                painter.drawLine(QPointF(zoom_end_x, 0), QPointF(zoom_end_x, self.height()))
                
                overlay_color = QColor(0, 0, 0, 80)
                painter.fillRect(QRectF(0, 0, zoom_start_x, self.height()), overlay_color)
                painter.fillRect(QRectF(zoom_end_x, 0, self.width() - zoom_end_x, self.height()), overlay_color)
        
        def draw_annotation_block(start_x, end_x, annotation=None, is_current=False, is_dragging=False, is_edge_hover=False):
            width = max(5, end_x - start_x)
            if end_x - start_x < 5:
                center = (start_x + end_x) / 2
                start_x = center - 2.5  # Half of min width
                end_x = center + 2.5
            
            height = self.height() * 0.4
            y_pos = (self.height() - height) / 2
            
            # Get posture color for this annotation
            base_color = QColor("#808080")  # Default gray
            if annotation and annotation.comments:
                try:
                    comment_data = json.loads(annotation.comments[0]["body"])
                    posture = next((item["selectedValue"] for item in comment_data if item["category"] == "POSTURE"), None)
                    if posture:
                        color_str = self.parent.annotation_manager.get_posture_color(posture)
                        base_color = QColor(color_str)
                except Exception as e:
                    print(f"Error getting annotation color: {str(e)}")
            
            # Draw annotation block with different colors based on state
            if is_dragging:
                color = QColor(base_color.red(), base_color.green(), base_color.blue(), 180)
            elif is_current:
                color = QColor(base_color.red(), base_color.green(), base_color.blue(), 160)
            else:
                color = QColor(base_color.red(), base_color.green(), base_color.blue(), 140)
            
            # Draw block
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            painter.drawRoundedRect(QRectF(start_x, y_pos, width, height), 4, 4)
            
            # Draw edge indicators when hovering or dragging
            if is_dragging or is_edge_hover:
                edge_color = QColor(255, 255, 255, 200)
                painter.setPen(QPen(edge_color, 2))
                marker_height = 8
                
                # Draw start edge markers
                if (is_dragging and self.dragging[0] == 'start') or \
                   (is_edge_hover and self.hover_edge[0] == 'start'):
                    painter.drawLine(QPointF(start_x, y_pos - marker_height), QPointF(start_x, y_pos))
                    painter.drawLine(QPointF(start_x, y_pos + height), QPointF(start_x, y_pos + height + marker_height))
                
                # Draw end edge markers
                if (is_dragging and self.dragging[0] == 'end') or \
                   (is_edge_hover and self.hover_edge[0] == 'end'):
                    painter.drawLine(QPointF(end_x, y_pos - marker_height), QPointF(end_x, y_pos))
                    painter.drawLine(QPointF(end_x, y_pos + height), QPointF(end_x, y_pos + height + marker_height))
        
        # Draw current annotation start line
        if hasattr(self.parent, 'current_annotation') and self.parent.current_annotation:
            if self.is_main_timeline:
                start_x = (self.parent.current_annotation.start_time / duration) * self.width()
            else:
                visible_duration = (self.parent.zoom_end - self.parent.zoom_start) * duration
                visible_start = self.parent.zoom_start * duration
                if visible_duration > 0:
                    relative_start = (self.parent.current_annotation.start_time - visible_start) / visible_duration
                    start_x = relative_start * self.width()
                    
                    if 0 <= start_x <= self.width():
                        painter.setPen(QPen(QColor(0, 255, 0), 2))  # 2px wide green line
                        painter.drawLine(QPointF(start_x, 0), QPointF(start_x, self.height()))
            
            if self.is_main_timeline:
                painter.setPen(QPen(QColor(0, 255, 0), 2))
                painter.drawLine(QPointF(start_x, 0), QPointF(start_x, self.height()))

        if hasattr(self.parent, 'annotations'):
            for annotation in self.parent.annotations:
                if self.is_main_timeline:
                    start_x = (annotation.start_time / duration) * self.width()
                    end_x = (annotation.end_time / duration) * self.width()
                else:
                    # Adjust annotation positions for zoomed view
                    visible_duration = (self.parent.zoom_end - self.parent.zoom_start) * duration
                    visible_start = self.parent.zoom_start * duration
                  
                    relative_start = (annotation.start_time - visible_start) / visible_duration
                    relative_end = (annotation.end_time - visible_start) / visible_duration
                    
                    start_x = relative_start * self.width()
                    end_x = relative_end * self.width()
                
                width = end_x - start_x
                
                if not self.is_main_timeline and (end_x < 0 or start_x > self.width()):
                    continue
                  
                if not self.is_main_timeline:
                    start_x = max(0, min(start_x, self.width()))
                    end_x = max(0, min(end_x, self.width()))
                    width = end_x - start_x
                
                if width > 0:  
                    is_dragging = self.dragging and self.dragging[1] == annotation
                    is_edge_hover = (
                        not self.dragging and 
                        self.hover_edge and 
                        self.hover_edge[1] == annotation
                    )

                    draw_annotation_block(
                        start_x, 
                        end_x, 
                        annotation=annotation,
                        is_current=False,
                        is_dragging=is_dragging,
                        is_edge_hover=is_edge_hover
                    )
                

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
