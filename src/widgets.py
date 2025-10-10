from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QPointF, QRectF
from PyQt6.QtGui import QPainter, QPen, QColor, QLinearGradient
import json

class TimelineWidget(QWidget):
    def __init__(self, parent=None, show_position=False, is_main_timeline=True):
        super().__init__(parent)
        self.app = parent
        self.show_position = show_position
        self.is_main_timeline = is_main_timeline
        self.setMinimumHeight(60)
        self.dragging = None
        
        self.hover_edge = None
        self.hover_annotation = None
        self.hover_pos = None
        
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.setMouseTracking(True)

    def mousePressEvent(self, event):
        if not hasattr(self.app, 'media_player'):
            return

        duration = self.app.media_player['_duration'] / 1000 or 1
        x = event.position().x()

        self.dragging = None

        if self.is_main_timeline:
            zoom_start_x = self.app.zoom_start * self.width()
            zoom_end_x = self.app.zoom_end * self.width()

            if abs(x - zoom_start_x) < 5:
                self.dragging = 'zoom_start'
                self.update()
                return
            elif abs(x - zoom_end_x) < 5:
                self.dragging = 'zoom_end'
                self.update()
                return

        for annotation in reversed(self.app.annotations):
            start_x, end_x = self._get_annotation_screen_coords(annotation, duration)

            if end_x < 0 or start_x > self.width():
                continue

            start_x = max(0, min(start_x, self.width()))
            end_x = max(0, min(end_x, self.width()))
            
            if abs(x - end_x) < 5:
                self.dragging = ('end', annotation)
                self.update()
                return
            elif abs(x - start_x) < 5:
                self.dragging = ('start', annotation)
                self.update()
                return

    def mouseReleaseEvent(self, event):
        self.dragging = None
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.update()

    def mouseMoveEvent(self, event):
        if not hasattr(self.app, 'media_player'):
            return

        duration = self.app.media_player['_duration'] / 1000 or 1
        x = event.position().x()

        if self.dragging:
            if self.dragging in ['zoom_start', 'zoom_end']:
                width_percent = max(0.0, min(1.0, x / self.width()))
                if self.dragging == 'zoom_start':
                    if width_percent < self.app.zoom_end - 0.05:
                        self.app.zoom_start = width_percent
                else:  # zoom_end
                    if width_percent > self.app.zoom_start + 0.05:
                        self.app.zoom_end = width_percent

                self.app.timeline_widget.update()
                self.app.second_timeline_widget.update()
                return

            elif isinstance(self.dragging, tuple):
                edge, annotation = self.dragging
                if self.is_main_timeline:
                    new_time = (x / self.width()) * duration
                else:
                    visible_duration = (self.app.zoom_end - self.app.zoom_start) * duration
                    visible_start = self.app.zoom_start * duration
                    new_time = visible_start + (x / self.width()) * visible_duration

                sorted_annotations = sorted(self.app.annotations, key=lambda x: x.start_time)
                current_index = None
                for idx, ann in enumerate(sorted_annotations):
                    if ann is annotation:
                        current_index = idx
                        break
                if edge == 'start':
                    if annotation.end_time - new_time < 0.1: # Min duration
                        return
                    if current_index > 0:
                        prev_annotation = sorted_annotations[current_index - 1]
                        if new_time < prev_annotation.end_time + 0.1:
                            new_time = prev_annotation.end_time + 0.1
                    annotation.start_time = max(0, new_time)
                else:  # 'end'
                    if new_time - annotation.start_time < 0.1: # Min duration
                        return
                    if current_index < len(sorted_annotations) - 1:
                        next_annotation = sorted_annotations[current_index + 1]
                        if new_time > next_annotation.start_time - 0.1:
                            new_time = next_annotation.start_time - 0.1
                    annotation.end_time = min(duration, new_time)

                self.app.timeline_widget.update()
                self.app.second_timeline_widget.update()
        else:
            old_hover_edge = self.hover_edge
            old_hover_annotation = self.hover_annotation
            
            found_edge = None
            found_body = None
            
            modifiers = event.modifiers()
            is_modifier_pressed = bool(modifiers & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier))

            for annotation in reversed(self.app.annotations):
                start_x, end_x = self._get_annotation_screen_coords(annotation, duration)
                
                if end_x < 0 or start_x > self.width():
                    continue

                # Check for edge hover first, as it has priority
                if abs(x - start_x) < 5:
                    found_edge = ('start', annotation)
                    break 
                if abs(x - end_x) < 5:
                    found_edge = ('end', annotation)
                    break
                
                # --- FIX: Check for body hover using only the horizontal position ---
                if is_modifier_pressed and not found_body:
                    if start_x <= x <= end_x:
                        found_body = annotation
            
            self.hover_edge = found_edge
            self.hover_annotation = found_body if not self.hover_edge and is_modifier_pressed else None
            
            if self.hover_edge:
                self.setCursor(Qt.CursorShape.SizeHorCursor)
            else:
                self.setCursor(Qt.CursorShape.ArrowCursor)

            if self.hover_annotation:
                self.hover_pos = event.position()

            if old_hover_edge != self.hover_edge or old_hover_annotation != self.hover_annotation:
                self.update()

    def leaveEvent(self, event):
        if self.hover_edge or self.hover_annotation:
            self.hover_edge = None
            self.hover_annotation = None
            self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        if not hasattr(self.app, 'media_player'):
            return
            
        duration = self.app.media_player['_duration'] / 1000 or 1

        if not self.is_main_timeline:
            visible_duration = (self.app.zoom_end - self.app.zoom_start) * duration
            if visible_duration <= 0: visible_duration = 1
            visible_start = self.app.zoom_start * duration
        
        painter.setPen(Qt.PenStyle.NoPen)
        if self.show_position:
            painter.setBrush(QColor(20, 20, 20))
            painter.drawRect(QRectF(0, 0, self.width(), self.height()))
            
            if duration > 0:
                if self.is_main_timeline:
                    progress_width = (self.app.media_player['_position'] / (duration * 1000)) * self.width()
                else:
    
                    position = self.app.media_player['_position'] / 1000  # Convert to seconds
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
                current_pos = (self.app.media_player['_position'] / (duration * 1000)) * self.width()
            else:
                position = self.app.media_player['_position'] / 1000
                relative_pos = (position - visible_start) / visible_duration
                current_pos = relative_pos * self.width()
                
            painter.setPen(QPen(QColor(200, 200, 200), 1))
            if 0 <= current_pos <= self.width():
                painter.drawLine(QPointF(current_pos, 0), QPointF(current_pos, self.height()))

            if self.is_main_timeline:
                zoom_start_x = self.app.zoom_start * self.width()
                zoom_end_x = self.app.zoom_end * self.width()
            
                painter.setPen(QPen(QColor(255, 0, 0), 2))
                painter.drawLine(QPointF(zoom_start_x, 0), QPointF(zoom_start_x, self.height()))
                painter.drawLine(QPointF(zoom_end_x, 0), QPointF(zoom_end_x, self.height()))
                
                overlay_color = QColor(0, 0, 0, 80)
                painter.fillRect(QRectF(0, 0, zoom_start_x, self.height()), overlay_color)
                painter.fillRect(QRectF(zoom_end_x, 0, self.width() - zoom_end_x, self.height()), overlay_color)

        def draw_annotation_block(start_x, end_x, annotation=None, is_dragging=False, is_edge_hover=False):
            width = max(5, end_x - start_x)
            if end_x - start_x < 5:
                center = (start_x + end_x) / 2
                start_x, end_x = center - 2.5, center + 2.5
            height = self.height() * 0.4
            y_pos = (self.height() - height) / 2
            
            # Get posture color for this annotation
            base_color = QColor("#808080")  # Default gray
            if annotation and annotation.comments:
                try:
                    comment_data = json.loads(annotation.comments[0]["body"])
                    posture = next((item.get("selectedValue") for item in comment_data if item.get("category") == "POSTURE"), None)
                    if posture:
                        color_str = self.app.annotation_manager.get_posture_color(posture)
                        base_color = QColor(color_str)
                except Exception as e:
                    print(f"Error getting annotation color: {e}")
            
            alpha = 180 if is_dragging else (160 if is_edge_hover else 140)
            color = QColor(base_color.red(), base_color.green(), base_color.blue(), alpha)
            
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            painter.drawRoundedRect(QRectF(start_x, y_pos, width, height), 4, 4)
            
            if is_dragging or is_edge_hover:
                painter.setPen(QPen(QColor(255, 255, 255, 200), 2))
                marker_height = 8
                edge_type = self.dragging[0] if is_dragging else self.hover_edge[0]
                if edge_type == 'start':
                    painter.drawLine(QPointF(start_x, y_pos - marker_height), QPointF(start_x, y_pos))
                    painter.drawLine(QPointF(start_x, y_pos + height), QPointF(start_x, y_pos + height + marker_height))
                if edge_type == 'end':
                    painter.drawLine(QPointF(end_x, y_pos - marker_height), QPointF(end_x, y_pos))
                    painter.drawLine(QPointF(end_x, y_pos + height), QPointF(end_x, y_pos + height + marker_height))

        if hasattr(self.app, 'current_annotation') and self.app.current_annotation:
            start_x, _ = self._get_annotation_screen_coords(self.app.current_annotation, duration)
            if 0 <= start_x <= self.width():
                painter.setPen(QPen(QColor(0, 255, 0), 2))
                painter.drawLine(QPointF(start_x, 0), QPointF(start_x, self.height()))

        if hasattr(self.app, 'annotations'):
            for annotation in self.app.annotations:
                start_x, end_x = self._get_annotation_screen_coords(annotation, duration)
                
                if end_x < 0 or start_x > self.width():
                    continue
                
                start_x = max(0, start_x)
                end_x = min(end_x, self.width())
                width = end_x - start_x
                
                if width > 0:
                    is_dragging = self.dragging and isinstance(self.dragging, tuple) and self.dragging[1] == annotation
                    is_edge_hover = not self.dragging and self.hover_edge and self.hover_edge[1] == annotation
                    draw_annotation_block(start_x, end_x, annotation=annotation, is_dragging=is_dragging, is_edge_hover=is_edge_hover)
                
                if width > 50:
                    painter.setPen(QPen(QColor(255, 255, 255)))
                    try:
                        comment_data = json.loads(annotation.comments[0]["body"])
                        posture = next((item.get("selectedValue") for item in comment_data if item.get("category") == "POSTURE"), "")
                        hlb_list = next((item.get("selectedValue") for item in comment_data if item.get("category") == "HIGH LEVEL BEHAVIOR"), [])
                        hlb = hlb_list if isinstance(hlb_list, list) else []

                        text = ", ".join(hlb[:2]) + ("..." if len(hlb) > 2 else "")
                        full_text = f"{posture} - {text}" if posture and text else posture or text
                        
                        block_height = self.height() * 0.4
                        block_y_pos = (self.height() - block_height) / 2
                        text_rect = QRectF(start_x + 4, block_y_pos, width - 8, block_height)
                        painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, full_text)
                    except Exception as e:
                        print(f"Error displaying annotation text: {e}")

        if self.hover_annotation and self.hover_pos:
            self._draw_hover_tooltip(painter, self.hover_pos, self.hover_annotation)

    def _get_annotation_screen_coords(self, annotation, duration):
        if self.is_main_timeline:
            start_x = (annotation.start_time / duration) * self.width()
            end_x = (annotation.end_time / duration) * self.width()
        else:
            visible_duration = (self.app.zoom_end - self.app.zoom_start) * duration
            visible_start = self.app.zoom_start * duration
            if visible_duration <= 0: return -1, -1
            start_x = ((annotation.start_time - visible_start) / visible_duration) * self.width()
            end_x = ((annotation.end_time - visible_start) / visible_duration) * self.width()
        return start_x, end_x

    def _format_annotation_for_tooltip(self, annotation):
        """Format annotation data into a readable single line for the tooltip."""
        if not annotation or not annotation.comments:
            return ""
        
        try:
            comment_list = json.loads(annotation.comments[0]['body'])
            
            def find_value(category_name):
                return next((item.get("selectedValue") for item in comment_list if item.get("category") == category_name), None)

            tooltip_items = [
                ("Posture", find_value("POSTURE")),
                ("Behavior", find_value("HIGH LEVEL BEHAVIOR")),
                ("PA Type", find_value("PHYSICAL ACTIVITY TYPE")),
                ("Params", find_value("BEHAVIORAL PARAMETERS")),
                ("Situation", find_value("EXPERIMENTAL SITUATION")),
                ("Notes", find_value("SPECIAL NOTES")),
            ]
            
            parts = []
            for label, value in tooltip_items:
                if not value:
                    continue
                
                if isinstance(value, list):
                    formatted_value = ", ".join(value)
                else:
                    formatted_value = str(value)
                
                parts.append(f"{label}: {formatted_value}")
            
            if not parts:
                return "No Labels Set"
            
            return " | ".join(parts)
            
        except (json.JSONDecodeError, IndexError, KeyError, TypeError) as e:
            print(f"Error formatting tooltip: {e}")
            return "Invalid Annotation Data"

    def _draw_hover_tooltip(self, painter, position, annotation):
        text = self._format_annotation_for_tooltip(annotation)
        if not text: return

        padding = 8
        font = painter.font()
        font.setPointSize(9)
        painter.setFont(font)
        
        text_rect = painter.fontMetrics().boundingRect(text) # Simplified calculation
        tooltip_rect = text_rect.adjusted(-padding, -padding, padding, padding)
        
        x = position.x() + 15
        y = position.y() - tooltip_rect.height() - 15

        if x + tooltip_rect.width() > self.width():
            x = self.width() - tooltip_rect.width() - 5
        if x < 5:
            x = 5
        if y < 5:
            y = position.y() + 15

        tooltip_rect.moveTo(int(x), int(y))

        painter.setBrush(QColor(0, 0, 0, 200))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(tooltip_rect, 5, 5)
        
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(tooltip_rect, Qt.AlignmentFlag.AlignCenter, text)