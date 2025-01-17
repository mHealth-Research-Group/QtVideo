from dataclasses import dataclass
import sys
import json
from datetime import datetime
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                           QHBoxLayout, QSlider, QMenu, QPushButton, QFileDialog,
                           QDialog, QLabel, QLineEdit, QTextEdit, QComboBox,
                           QDialogButtonBox, QInputDialog, QMessageBox, QListWidget,
                           QAbstractItemView)
from PyQt6.QtMultimedia import QMediaPlayer
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtCore import Qt, QUrl, QPointF, QRectF, QTime
from PyQt6.QtGui import QPainter, QPen, QColor, QAction, QKeyEvent, QLinearGradient

@dataclass
class TimelineAnnotation:
    def __init__(self, start_time=0, end_time=0):
        self.start_time = start_time
        self.end_time = end_time
        self.posture = []
        self.hlb = [] 
        self.pa_type = []
        self.behavioral_params = []
        self.exp_situation = []
        self.special_notes = ""

class AnnotationDialog(QDialog):
    def __init__(self, annotation=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Category Choices")
        self.setModal(True)
        self.setMinimumWidth(600)
        self.setMinimumHeight(800)
        
        layout = QVBoxLayout(self)
        
        # Initialize list widgets
        self.posture_list = QListWidget()
        self.hlb_list = QListWidget()
        self.pa_list = QListWidget()
        self.bp_list = QListWidget()
        self.es_list = QListWidget()
        
        # Set multi-selection mode for all lists
        for lst in [self.posture_list, self.hlb_list, self.pa_list, self.bp_list, self.es_list]:
            lst.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
            lst.setMinimumHeight(120)
        
        # Load categories from CSV
        self.load_categories()
        
        # POSTURE (Key 1)
        posture_layout = QVBoxLayout()
        posture_layout.addWidget(QLabel("POSTURE (Key 1):"))
        posture_layout.addWidget(self.posture_list)
        layout.addLayout(posture_layout)
        
        # HIGH LEVEL BEHAVIOR (Key 2)
        hlb_layout = QVBoxLayout()
        hlb_layout.addWidget(QLabel("HIGH LEVEL BEHAVIOR (Key 2):"))
        hlb_layout.addWidget(self.hlb_list)
        layout.addLayout(hlb_layout)
        
        # PA TYPE (Key 3)
        pa_layout = QVBoxLayout()
        pa_layout.addWidget(QLabel("PA TYPE (Key 3):"))
        pa_layout.addWidget(self.pa_list)
        layout.addLayout(pa_layout)
        
        # Behavioral Parameters (Key 4)
        bp_layout = QVBoxLayout()
        bp_layout.addWidget(QLabel("Behavioral Parameters (Key 4):"))
        bp_layout.addWidget(self.bp_list)
        layout.addLayout(bp_layout)
        
        # Experimental situation (Key 5)
        es_layout = QVBoxLayout()
        es_layout.addWidget(QLabel("Experimental situation (Key 5):"))
        es_layout.addWidget(self.es_list)
        layout.addLayout(es_layout)
        
        # Special Notes (Key 6)
        notes_layout = QHBoxLayout()
        notes_layout.addWidget(QLabel("Special Notes (Key 6):"))
        self.notes_edit = QLineEdit()
        self.notes_edit.setMaxLength(255)
        self.notes_edit.setText("")
        notes_layout.addWidget(self.notes_edit)
        layout.addLayout(notes_layout)
        
        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
        # Set values if annotation provided
        if annotation:
            for posture in annotation.posture:
                items = self.posture_list.findItems(posture, Qt.MatchFlag.MatchExactly)
                for item in items:
                    item.setSelected(True)
            for hlb in annotation.hlb:
                items = self.hlb_list.findItems(hlb, Qt.MatchFlag.MatchExactly)
                for item in items:
                    item.setSelected(True)
            for pa_type in annotation.pa_type:
                items = self.pa_list.findItems(pa_type, Qt.MatchFlag.MatchExactly)
                for item in items:
                    item.setSelected(True)
            for bp in annotation.behavioral_params:
                items = self.bp_list.findItems(bp, Qt.MatchFlag.MatchExactly)
                for item in items:
                    item.setSelected(True)
            for es in annotation.exp_situation:
                items = self.es_list.findItems(es, Qt.MatchFlag.MatchExactly)
                for item in items:
                    item.setSelected(True)
            self.notes_edit.setText(annotation.special_notes)
            
    def load_categories(self):
        """Load categories from the CSV file"""
        try:
            import csv
            with open('categories.csv', 'r') as f:
                reader = csv.DictReader(f)
                categories = {
                    'POSTURE': ["Posture_Unlabeled"],
                    'HIGH LEVEL BEHAVIOR': ["HLB_Unlabeled"],
                    'PA TYPE': ["PA_Type_Unlabeled"],
                    'Behavioral Parameters': ["CP_Unlabeled"],
                    'Experimental situation': ["ES_Unlabeled"]
                }
                
                for row in reader:
                    if row['POSTURE']:
                        categories['POSTURE'].append(row['POSTURE'])
                    if row['HIGH LEVEL BEHAVIOR']:
                        categories['HIGH LEVEL BEHAVIOR'].append(row['HIGH LEVEL BEHAVIOR'])
                    if row['PA TYPE']:
                        categories['PA TYPE'].append(row['PA TYPE'])
                    if row['Behavioral Parameters']:
                        categories['Behavioral Parameters'].append(row['Behavioral Parameters'])
                    if row['Experimental situation']:
                        categories['Experimental situation'].append(row['Experimental situation'])
                
                self.posture_list.addItems(categories['POSTURE'])
                self.hlb_list.addItems(categories['HIGH LEVEL BEHAVIOR'])
                self.pa_list.addItems(categories['PA TYPE'])
                self.bp_list.addItems(categories['Behavioral Parameters'])
                self.es_list.addItems(categories['Experimental situation'])
                
        except Exception as e:
            print(f"Error loading categories: {str(e)}")
            # Add default items if CSV loading fails
            self.posture_list.addItem("Posture_Unlabeled")
            self.hlb_list.addItem("HLB_Unlabeled")
            self.pa_list.addItem("PA_Type_Unlabeled")
            self.bp_list.addItem("CP_Unlabeled")
            self.es_list.addItem("ES_Unlabeled")

class VideoPlayerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Video Annotator")
        self.setGeometry(100, 100, 1024, 768)
        
        # Initialize data storage
        self.annotations = []  # List of TimelineAnnotation objects
        self.current_annotation = None  # For tracking annotation in progress
        
        self.setupUI()
        self.setupShortcuts()
        
    def setupUI(self):
        # Create central widget and layout
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Create video container
        video_container = QWidget()
        video_container.setStyleSheet("background-color: black;")
        video_layout = QVBoxLayout(video_container)
        
        # Create video player
        self.media_player = QMediaPlayer()
        self.video_widget = QVideoWidget()
        video_layout.addWidget(self.video_widget)
        layout.addWidget(video_container)
        
        # Create timelines container
        timelines_container = QWidget()
        timelines_layout = QVBoxLayout(timelines_container)
        timelines_layout.setSpacing(4)
        timelines_layout.setContentsMargins(4, 4, 4, 4) 
        
        # Main timeline with annotations
        main_timeline_container = QWidget()
        main_timeline_container.setMinimumHeight(50)
        self.timeline = QSlider(Qt.Orientation.Horizontal)
        self.timeline.sliderMoved.connect(self.setPosition)
        
        class TimelineWidget(QWidget):
            def __init__(self, parent=None, show_position=False):
                super().__init__(parent)
                self.parent = parent
                self.show_position = show_position
                self.setMinimumHeight(60)
                
            def paintEvent(self, event):
                painter = QPainter(self)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                
                if not hasattr(self.parent, 'media_player'):
                    return
                    
                duration = self.parent.media_player.duration() or 1
                
                timeline_height = self.height() * 0.4
                annotation_height = self.height() * 0.6
                
                # Draw container border
                painter.setPen(QPen(QColor(200, 200, 200), 1))
                painter.drawRect(QRectF(0, 0, self.width() - 1, self.height() - 1))
                
                # Draw timeline background with gradient
                gradient = QLinearGradient(0, annotation_height, 0, self.height())
                gradient.setColorAt(0, QColor(240, 240, 240))
                gradient.setColorAt(1, QColor(220, 220, 220))
                painter.fillRect(QRectF(0, annotation_height, self.width(), timeline_height), gradient)
                
                # Draw separator line
                painter.setPen(QPen(QColor(180, 180, 180), 1))
                painter.drawLine(QPointF(0, annotation_height), QPointF(self.width(), annotation_height))
                
                # Draw red lines at start and end (for both timelines)
                painter.setPen(QPen(QColor(255, 0, 0), 2))
                painter.drawLine(QPointF(0, annotation_height), QPointF(0, self.height()))
                painter.drawLine(QPointF(self.width() - 2, annotation_height), 
                               QPointF(self.width() - 2, self.height())) 
                
                # Draw current position line
                current_pos = (self.parent.media_player.position() / duration) * self.width()
                painter.setPen(QPen(QColor(0, 120, 215), 2))
                painter.drawLine(QPointF(current_pos, 0), QPointF(current_pos, self.height()))
                
                def draw_annotation_block(start_x, end_x, is_current=False):
                    width = end_x - start_x
                    
                    gradient = QLinearGradient(start_x, 0, end_x, 0)
                    if is_current:
                        gradient.setColorAt(0, QColor(139, 69, 19, 160))
                        gradient.setColorAt(1, QColor(139, 69, 19, 140))
                    else:
                        gradient.setColorAt(0, QColor(139, 69, 19, 140))
                        gradient.setColorAt(1, QColor(139, 69, 19, 120))
                    
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(gradient)
                
                    block_margin = 1
                    painter.drawRect(QRectF(start_x + block_margin, block_margin, 
                                          width - 2*block_margin, annotation_height - 2*block_margin))
                    painter.drawRect(QRectF(start_x + block_margin, annotation_height + block_margin,
                                          width - 2*block_margin, timeline_height - 2*block_margin))
                
                if hasattr(self.parent, 'current_annotation') and self.parent.current_annotation:
                    start_x = (self.parent.current_annotation.start_time / duration) * self.width()
                    end_x = (self.parent.media_player.position() / duration) * self.width()
                    draw_annotation_block(start_x, end_x, True)

                if hasattr(self.parent, 'annotations'):
                    for annotation in self.parent.annotations:
                        start_x = (annotation.start_time / duration) * self.width()
                        end_x = (annotation.end_time / duration) * self.width()
                        width = end_x - start_x
                        
                        # Draw annotation block
                        draw_annotation_block(start_x, end_x)
                        
                        # Draw annotation text if enough space
                        if width > 50:
                            painter.setPen(QPen(QColor(255, 255, 255)))
                            text = ", ".join(annotation.posture[:2])
                            if len(annotation.posture) > 2:
                                text += "..."
                            text_rect = QRectF(start_x + 2, 2, width - 4, annotation_height/2 - 2)
                            painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, text)
                            
                            text = ", ".join(annotation.hlb[:2])
                            if len(annotation.hlb) > 2:
                                text += "..."
                            text_rect = QRectF(start_x + 2, annotation_height/2, width - 4, annotation_height/2 - 2)
                            painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, text)
                        
                        start_time = QTime(0, 0).addMSecs(annotation.start_time).toString('mm:ss')
                        end_time = QTime(0, 0).addMSecs(annotation.end_time).toString('mm:ss')
                        
                        time_bg_color = QColor(255, 255, 255, 180) #TODO: Make this a class variable
                        painter.setPen(Qt.PenStyle.NoPen)
                        painter.setBrush(time_bg_color)
                        
                        # Start time
                        time_rect = QRectF(start_x, annotation_height + timeline_height - 18, 
                                         45, 16)
                        painter.drawRect(time_rect)
                        painter.setPen(QPen(QColor(0, 0, 0)))
                        painter.drawText(time_rect, Qt.AlignmentFlag.AlignCenter, start_time)
                        
                        # End time if enough space
                        if width > 60:
                            time_rect = QRectF(end_x - 45, annotation_height + timeline_height - 18,
                                             45, 16)
                            painter.setPen(Qt.PenStyle.NoPen)
                            painter.setBrush(time_bg_color)
                            painter.drawRect(time_rect)
                            painter.setPen(QPen(QColor(0, 0, 0)))
                            painter.drawText(time_rect, Qt.AlignmentFlag.AlignCenter, end_time)
        
        self.timeline_widget = TimelineWidget(self, show_position=False)
        main_timeline_layout = QVBoxLayout(main_timeline_container)
        main_timeline_layout.setSpacing(2)
        main_timeline_layout.setContentsMargins(0, 0, 0, 0)
        main_timeline_layout.addWidget(self.timeline_widget)
        
        # Style the timeline slider
        self.timeline.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 3px;
                background: #ddd;
            }
            QSlider::handle:horizontal {
                background: #4a90e2;
                width: 12px;
                margin: -4px 0;
                border-radius: 6px;
            }
        """)
        main_timeline_layout.addWidget(self.timeline)
        timelines_layout.addWidget(main_timeline_container)
        
        second_timeline_container = QWidget()
        second_timeline_container.setMinimumHeight(50)
        second_timeline_container.setStyleSheet("""
            QWidget {
                background-color: #f8f8f8;
                border: 1px solid #ddd;
                border-radius: 4px;
            }
            QLabel {
                color: #333;
                font-size: 11px;
                padding: 2px;
            }
        """)
        second_timeline_layout = QVBoxLayout(second_timeline_container)
        second_timeline_layout.setSpacing(2) 
        second_timeline_layout.setContentsMargins(0, 0, 0, 0)
        
        self.second_timeline_widget = TimelineWidget(self, show_position=True)
        second_timeline_layout.addWidget(self.second_timeline_widget)
        
        self.time_label = QLabel("00:00:00 / 00:00:00")
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        second_timeline_layout.addWidget(self.time_label)
        
        timelines_layout.addWidget(second_timeline_container)
        
        layout.addWidget(timelines_container)
        
        controls_layout = QHBoxLayout()
        
        button_container = QWidget()
        button_container.setStyleSheet("""
            QPushButton {
                padding: 8px 16px;
                background-color: #4a90e2;
                color: white;
                border: none;
                border-radius: 4px;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #357abd;
            }
            QPushButton:pressed {
                background-color: #2a5f9e;
            }
        """)
        button_layout = QHBoxLayout(button_container)
        button_layout.setSpacing(10)
        
        self.open_button = QPushButton("Open Video")
        self.open_button.setToolTip("Open a video file for annotation")
        self.open_button.clicked.connect(self.openFile)
        
        self.play_pause_button = QPushButton("Play")
        self.play_pause_button.setToolTip("Play/Pause the video")
        self.play_pause_button.clicked.connect(self.togglePlayPause)
        
        self.save_json_button = QPushButton("Save JSON")
        self.save_json_button.setToolTip("Save annotations to JSON file")
        self.save_json_button.clicked.connect(self.saveAnnotations)
        self.save_json_button.hide()  # Initially hidden
        
        self.load_json_button = QPushButton("Load JSON")
        self.load_json_button.setToolTip("Load annotations from JSON file")
        self.load_json_button.clicked.connect(self.loadAnnotations)
        self.load_json_button.hide()  # Initially hidden
        
        for button in [self.open_button, self.play_pause_button, self.save_json_button, self.load_json_button]:
            button_layout.addWidget(button)
        
        controls_layout.addWidget(button_container)
        layout.addLayout(controls_layout)
        
        self.media_player.setVideoOutput(self.video_widget)
        self.media_player.playbackStateChanged.connect(self.updatePlayPauseButton)
        self.media_player.positionChanged.connect(self.positionChanged)
        self.media_player.durationChanged.connect(self.durationChanged)
        
    def setupShortcuts(self):
        # Shortcut for annotation mode (a)
        self.annotation_shortcut = QAction("Annotate", self)
        self.annotation_shortcut.setShortcut("a")
        self.annotation_shortcut.triggered.connect(self.toggleAnnotation)
        self.addAction(self.annotation_shortcut)
        
        # Shortcut for editing annotation (g)
        self.edit_shortcut = QAction("Edit", self)
        self.edit_shortcut.setShortcut("g")
        self.edit_shortcut.triggered.connect(self.editAnnotation)
        self.addAction(self.edit_shortcut)
        
    def openFile(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Open Video", "", "Video Files (*.mp4 *.avi *.mkv)")
        if filename:
            self.media_player.setSource(QUrl.fromLocalFile(filename))
            # Start playing then immediately pause
            self.media_player.play()
            self.media_player.pause()
            self.updatePlayPauseButton()
            
            # Show JSON buttons after video is loaded
            self.save_json_button.show()
            self.load_json_button.show()
            
    def togglePlayPause(self):
        if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.media_player.pause()
        else:
            self.media_player.play()
            
    def updatePlayPauseButton(self):
        if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.play_pause_button.setText("Pause")
        else:
            self.play_pause_button.setText("Play")
            
    def setPosition(self, position):
        self.media_player.setPosition(position)
        
    def positionChanged(self, position):
        self.timeline.setValue(position)
        duration = self.media_player.duration()
        
        current = QTime(0, 0).addMSecs(position).toString('hh:mm:ss')
        total = QTime(0, 0).addMSecs(duration).toString('hh:mm:ss')
        self.time_label.setText(f"{current} / {total}")
        
        # Update both timeline visualizations
        self.timeline_widget.update()
        self.second_timeline_widget.update()
        
    def durationChanged(self, duration):
        self.timeline.setRange(0, duration)
        
    def toggleAnnotation(self):
        current_time = self.media_player.position()
        if self.current_annotation is None:
            self.current_annotation = TimelineAnnotation(start_time=current_time)
        else:
            self.current_annotation.end_time = current_time
            self.annotations.append(self.current_annotation)
            self.current_annotation = None
            self.updateAnnotationTimeline()
            
    def editAnnotation(self):
        current_time = self.media_player.position()
        for annotation in self.annotations:
            if annotation.start_time <= current_time <= annotation.end_time:
                dialog = AnnotationDialog(annotation, self)
                if dialog.exec():
                    annotation.posture = [item.text() for item in dialog.posture_list.selectedItems()]
                    annotation.hlb = [item.text() for item in dialog.hlb_list.selectedItems()]
                    annotation.pa_type = [item.text() for item in dialog.pa_list.selectedItems()]
                    annotation.behavioral_params = [item.text() for item in dialog.bp_list.selectedItems()]
                    annotation.exp_situation = [item.text() for item in dialog.es_list.selectedItems()]
                    annotation.special_notes = dialog.notes_edit.text()
                break
                
    def saveAnnotations(self):
        filename, _ = QFileDialog.getSaveFileName(self, "Save Annotations", "", "JSON Files (*.json)")
        if filename:
            annotations_data = []
            for annotation in self.annotations:
                annotations_data.append({
                    'start_time': annotation.start_time,
                    'end_time': annotation.end_time,
                    'posture': annotation.posture,
                    'hlb': annotation.hlb,
                    'pa_type': annotation.pa_type,
                    'behavioral_params': annotation.behavioral_params,
                    'exp_situation': annotation.exp_situation,
                    'special_notes': annotation.special_notes
                })
            
            try:
                with open(filename, 'w') as f:
                    json.dump(annotations_data, f, indent=4)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save annotations: {str(e)}")
    
    def loadAnnotations(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Load Annotations", "", "JSON Files (*.json)")
        if filename:
            try:
                with open(filename, 'r') as f:
                    annotations_data = json.load(f)
                
                self.annotations = []
                for data in annotations_data:
                    annotation = TimelineAnnotation()
                    annotation.start_time = data['start_time']
                    annotation.end_time = data['end_time']
                    annotation.posture = data['posture']
                    annotation.hlb = data['hlb']
                    annotation.pa_type = data['pa_type']
                    annotation.behavioral_params = data['behavioral_params']
                    annotation.exp_situation = data['exp_situation']
                    annotation.special_notes = data['special_notes']
                    self.annotations.append(annotation)
                
                self.updateAnnotationTimeline()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load annotations: {str(e)}")
    
    def updateAnnotationTimeline(self):
        self.timeline_widget.update()
        
    def keyPressEvent(self, event: QKeyEvent):
        if event.key() >= Qt.Key.Key_1 and event.key() <= Qt.Key.Key_6:
            # TODO: Implement quick category selection
            pass
        super().keyPressEvent(event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    player = VideoPlayerApp()
    player.show()
    sys.exit(app.exec())
