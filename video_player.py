from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                           QSlider, QPushButton, QFileDialog, QLabel, QMessageBox,
                           QMenu)
from PyQt6.QtMultimedia import QMediaPlayer
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtCore import Qt, QUrl, QTime, QTimer
from PyQt6.QtGui import QAction, QKeyEvent, QTransform

from models import TimelineAnnotation
from widgets import TimelineWidget
from dialogs import AnnotationDialog
from shortcuts import ShortcutManager
from annotation_manager import AnnotationManager
import json

class VideoPlayerApp(QMainWindow):
    PREVIEW_OFFSET = 3000  # 3 seconds offset for preview player in milliseconds
    SYNC_THRESHOLD = 100
    MIN_ZOOM_DURATION = 600000 # 10 minutes
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Video Annotator")
        self.setGeometry(100, 100, 1280, 800)
        self.setStyleSheet("""
            QMainWindow {
                background-color: #2b2b2b;
                color: #ffffff;
            }
            QLabel {
                color: #ffffff;
                font-size: 12px;
            }
        """)
        
        # Initialize data storage
        self.annotations = []  # List of TimelineAnnotation objects
        self.current_annotation = None  # For tracking annotation in progress
        self.video_hash = "NA"  # Placeholder for video hash
        
        # Zoom region (as percentage of total duration)
        self.zoom_start = 0.0
        self.zoom_end = 1.0  # Default to showing first 100%
        
        self.setupUI()
        self.annotation_manager = AnnotationManager(self)
        self.shortcut_manager = ShortcutManager(self)
        
    def setupUI(self):
        # Create central widget and layout
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Create video container with padding and border
        video_container = QWidget()
        video_container.setStyleSheet("""
            QWidget {
                background-color: #1a1a1a;
                border: 2px solid #3a3a3a;
                border-radius: 8px;
                margin: 10px;
            }
        """)
        video_container.setMinimumHeight(400)
        
        # Create horizontal layout for video widgets
        video_container_layout = QHBoxLayout(video_container)
        video_container_layout.setContentsMargins(10, 10, 10, 10)
        video_container_layout.setSpacing(10)
        
        # Left video widget
        left_video_container = QWidget()
        left_video_layout = QVBoxLayout(left_video_container)
        left_video_layout.setContentsMargins(0, 0, 0, 0)
        
        # Right video widget
        right_video_container = QWidget()
        right_video_layout = QVBoxLayout(right_video_container)
        right_video_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create media players and widgets
        self.media_player = QMediaPlayer()
        self.media_player_preview = QMediaPlayer()  # Preview player
        
        self.video_widget = QVideoWidget()
        self.video_widget_preview = QVideoWidget()  # Preview widget
        
        # Set up video outputs
        self.media_player.setVideoOutput(self.video_widget)
        self.media_player_preview.setVideoOutput(self.video_widget_preview)
        
        # Apply styling to both video widgets
        video_widget_style = """
            QVideoWidget {
                background-color: #000000;
                border-radius: 4px;
            }
        """
        self.video_widget.setStyleSheet(video_widget_style)
        self.video_widget_preview.setStyleSheet(video_widget_style)
        
        # Add video widgets to their containers
        left_video_layout.addWidget(self.video_widget)
        right_video_layout.addWidget(self.video_widget_preview)
        
        # Labels for each video widget
        # main_label = QLabel("Current")
        # preview_label = QLabel("Preview (+3s)")
        # main_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # left_video_layout.addWidget(main_label)
        # right_video_layout.addWidget(preview_label)
        
        # Add containers to main video layout
        video_container_layout.addWidget(left_video_container)
        video_container_layout.addWidget(right_video_container)
        
        layout.addWidget(video_container, stretch=1)
        
        # Rest of the UI components...
        # Create timelines container with improved styling
        timelines_container = QWidget()
        timelines_container.setStyleSheet("""
            QWidget {
                background-color: #2b2b2b;
                border: 1px solid #3a3a3a;
                border-radius: 6px;
            }
        """)
        timelines_layout = QVBoxLayout(timelines_container)
        timelines_layout.setSpacing(8)
        timelines_layout.setContentsMargins(12, 12, 12, 12)
        
        # Main timeline with annotations
        main_timeline_container = QWidget()
        main_timeline_container.setMinimumHeight(50)
        self.timeline = QSlider(Qt.Orientation.Horizontal)
        self.timeline.sliderMoved.connect(lambda pos: self.setPosition(pos, from_main=True))
        
        self.timeline_widget = TimelineWidget(self, show_position=False, is_main_timeline=True)
        main_timeline_layout = QVBoxLayout(main_timeline_container)
        main_timeline_layout.setSpacing(2)
        main_timeline_layout.setContentsMargins(0, 0, 0, 0)
        main_timeline_layout.addWidget(self.timeline_widget)
        
        # Style the timeline slider with modern look
        self.timeline.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 4px;
                background: #404040;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #4a90e2;
                width: 16px;
                height: 16px;
                margin: -6px 0;
                border-radius: 8px;
                border: 2px solid #2b2b2b;
            }
            QSlider::handle:horizontal:hover {
                background: #5aa0f2;
            }
            QSlider::sub-page:horizontal {
                background: #4a90e2;
                border-radius: 2px;
            }
        """)
        main_timeline_layout.addWidget(self.timeline)
        timelines_layout.addWidget(main_timeline_container)
        
        second_timeline_container = QWidget()
        second_timeline_container.setMinimumHeight(50)
        second_timeline_container.setStyleSheet("""
            QWidget {
                background-color: #1a1a1a;
                border: none;
            }
            QLabel {
                color: #ffffff;
                font-size: 12px;
                padding: 4px;
                background: none;
                margin: 2px;
            }
        """)
        second_timeline_layout = QVBoxLayout(second_timeline_container)
        second_timeline_layout.setSpacing(2) 
        second_timeline_layout.setContentsMargins(0, 0, 0, 0)
        
        # Second timeline (zoomed view)
        self.second_timeline = QSlider(Qt.Orientation.Horizontal)
        self.second_timeline.sliderMoved.connect(lambda pos: self.setPosition(pos, from_main=False))
        self.second_timeline_widget = TimelineWidget(self, show_position=True, is_main_timeline=False)
        second_timeline_layout.addWidget(self.second_timeline_widget)
        
        self.time_label = QLabel("00:00:00 / 00:00:00")
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        second_timeline_layout.addWidget(self.time_label)
        
        timelines_layout.addWidget(second_timeline_container)
        
        layout.addWidget(timelines_container)
        
        # Keyboard shortcuts help section
        shortcuts_container = QWidget()
        shortcuts_container.setStyleSheet("""
            QWidget {
                background-color: #1a1a1a;
                border: 1px solid #3a3a3a;
                border-radius: 8px;
                padding: 15px;
                margin: 8px;
            }
            QLabel {
                color: #ffffff;
                font-size: 13px;
                padding: 4px 8px;
                selection-background-color: transparent;
                selection-color: #ffffff;
            }
            QLabel[isHeader="true"] {
                color: #4a90e2;
                font-size: 14px;
                font-weight: bold;
                padding: 8px;
                margin-bottom: 8px;
                border-bottom: 2px solid #4a90e2;
            }
            QLabel[isShortcut="true"] {
                background-color: #2a2a2a;
                border-radius: 4px;
                margin: 2px 0px;
            }
            QLabel[isShortcut="true"]:hover {
                background-color: #353535;
            }
            QWidget[isColumn="true"] {
                background-color: #222222;
                border-radius: 6px;
                padding: 10px;
                margin: 5px;
            }
        """)
        shortcuts_layout = QHBoxLayout(shortcuts_container)
        shortcuts_layout.setSpacing(15)
        
        # Create columns for different shortcut categories
        video_shortcuts = QVBoxLayout()
        header = QLabel("🎥 Video Controls")
        header.setProperty("isHeader", True)
        video_shortcuts.addWidget(header)
        
        for shortcut in [
            "⎵ Spacebar - Play/Pause",
            "←/→ - Skip 10s backward/forward",
            "↑/↓ - Increase/decrease speed",
            "R - Reset speed to 1x"
        ]:
            label = QLabel(shortcut)
            label.setProperty("isShortcut", True)
            video_shortcuts.addWidget(label)
        
        label_shortcuts = QVBoxLayout()
        header = QLabel("🏷️ Labeling Controls")
        header.setProperty("isHeader", True)
        label_shortcuts.addWidget(header)
        
        for shortcut in [
            "A - Start/Stop labeling",
            "Z - Cancel labeling",
            "S - Delete label",
            "G - Open label dialog",
            "P - Split label"
        ]:
            label = QLabel(shortcut)
            label.setProperty("isShortcut", True)
            label_shortcuts.addWidget(label)
        
        nav_shortcuts = QVBoxLayout()
        header = QLabel("🔍 Navigation")
        header.setProperty("isHeader", True)
        nav_shortcuts.addWidget(header)
        
        for shortcut in [
            "Shift+←/→ - Previous/Next label",
            "N - Merge with previous",
            "M - Merge with next",
            "Shift+↑/↓ - Adjust preview skip"
        ]:
            label = QLabel(shortcut)
            label.setProperty("isShortcut", True)
            nav_shortcuts.addWidget(label)
        
        dialog_shortcuts = QVBoxLayout()
        header = QLabel("📝 Dialog Controls")
        header.setProperty("isHeader", True)
        dialog_shortcuts.addWidget(header)
        
        for shortcut in [
            "1 - Select Posture",
            "2 - Select High Level Behavior",
            "3 - Select PA Type",
            "4 - Select Behavioral Parameters",
            "5 - Select Experimental Situation"
        ]:
            label = QLabel(shortcut)
            label.setProperty("isShortcut", True)
            dialog_shortcuts.addWidget(label)
        
        # Add all columns to the shortcuts container
        for column in [video_shortcuts, label_shortcuts, nav_shortcuts, dialog_shortcuts]:
            container = QWidget()
            container.setProperty("isColumn", True)
            container.setLayout(column)
            for i in range(column.count()):
                widget = column.itemAt(i).widget()
                if isinstance(widget, QLabel):
                    widget.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
            shortcuts_layout.addWidget(container)
        
        layout.addWidget(shortcuts_container)
        
        # Controls section
        controls_container = QWidget()
        controls_container.setStyleSheet("""
            QWidget {
                background-color: #1a1a1a;
                border: 1px solid #3a3a3a;
                border-radius: 6px;
                margin: 8px;
            }
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
        controls_layout = QHBoxLayout(controls_container)
        controls_layout.setSpacing(10)
        controls_layout.setContentsMargins(12, 8, 12, 8)
        
        # Left side controls
        left_controls = QWidget()
        left_layout = QHBoxLayout(left_controls)
        left_layout.setSpacing(10)
        left_layout.setContentsMargins(0, 0, 0, 0)

        self.play_pause_button = QPushButton("Play")
        self.play_pause_button.setToolTip("Play/Pause the video")
        self.play_pause_button.clicked.connect(self.togglePlayPause)

        # Speed indicator label
        self.speed_label = QLabel("1.0x")
        self.speed_label.setStyleSheet("""
            QLabel {
                color: white;
                padding: 8px;
                background-color: #2a2a2a;
                border-radius: 4px;
                min-width: 50px;
                text-align: center;
            }
        """)

        left_layout.addWidget(self.play_pause_button)
        left_layout.addWidget(self.speed_label)

        # Right side controls
        right_controls = QWidget()
        right_layout = QHBoxLayout(right_controls)
        right_layout.setSpacing(10)
        right_layout.setContentsMargins(0, 0, 0, 0)

        self.open_button = QPushButton("Open Video")
        self.open_button.setToolTip("Open a video file for annotation")
        self.open_button.clicked.connect(self.openFile)

        # Gear button with menu
        self.gear_button = QPushButton("⚙")
        self.gear_button.setToolTip("Settings")
        self.gear_button.setStyleSheet("""
            QPushButton {
                padding: 8px 12px;
                background-color: #4a90e2;
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 16px;
                min-width: 40px;
            }
            QPushButton:hover {
                background-color: #357abd;
            }
            QPushButton:pressed {
                background-color: #2a5f9e;
            }
        """)
        
        # Create settings menu
        self.settings_menu = QMenu(self)
        self.settings_menu.setStyleSheet("""
            QMenu {
                background-color: #2b2b2b;
                border: 1px solid #3a3a3a;
            }
            QMenu::item {
                padding: 8px 20px;
                color: white;
            }
            QMenu::item:selected {
                background-color: #4a90e2;
            }
        """)
        
        # Add menu actions
        self.settings_menu.addAction("Load JSON", self.loadAnnotations)
        self.settings_menu.addAction("Export Labels", self.saveAnnotations)
        self.settings_menu.addAction("New Video", self.openFile)
        self.settings_menu.addAction("Rotate Video", self.rotateVideo)
        
        # Connect gear button to show menu at button position
        self.gear_button.clicked.connect(self.showSettingsMenu)
        
        right_layout.addWidget(self.open_button)
        right_layout.addWidget(self.gear_button)

        # Add left and right controls to main controls layout
        controls_layout.addWidget(left_controls)
        controls_layout.addStretch()
        controls_layout.addWidget(right_controls)

        layout.addWidget(controls_container)
        
        # Connect signals for syncing media players
        self.media_player.playbackStateChanged.connect(self.updatePlayPauseButton)
        self.media_player.positionChanged.connect(self.positionChanged)
        self.media_player.durationChanged.connect(self.durationChanged)
        self.media_player.playbackRateChanged.connect(self.updateSpeedLabel)

        self.timeline.sliderReleased.connect(
            lambda: self._sync_preview_position(self.timeline.value())
        )

    def showSettingsMenu(self):
        # Show menu at the bottom right of the gear button
        pos = self.gear_button.mapToGlobal(self.gear_button.rect().bottomRight())
        # Adjust position to align with right edge
        pos.setX(pos.x() - self.settings_menu.sizeHint().width())
        self.settings_menu.exec(pos)
            
    def _sync_preview_position(self, position):
        """
        Synchronize preview player position with reduced updates to prevent stuttering.
        Only updates if the difference exceeds the threshold or during seek operations.
        """
        if not self.media_player.duration():
            return

        target_preview_pos = position + self.PREVIEW_OFFSET
        current_preview_pos = self.media_player_preview.position()
        
        # Calculate the difference between current and target preview position
        position_diff = abs(target_preview_pos - current_preview_pos)
        
        # Only update if:
        # 1. The difference is significant (exceeds threshold)
        # 2. Or if we're in a seek operation (timeline drag)
        if position_diff > self.SYNC_THRESHOLD or self.timeline.isSliderDown():
            # Ensure we don't exceed video duration
            max_position = self.media_player.duration()
            if target_preview_pos <= max_position:
                self.media_player_preview.setPosition(target_preview_pos)
            else:
                self.media_player_preview.setPosition(max_position)
            self.last_preview_update = target_preview_pos

    def openFile(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Open Video", "", "Video Files (*.mp4 *.avi *.mkv)")
        if filename:
            url = QUrl.fromLocalFile(filename)
            self.media_player.setSource(url)
            self.media_player_preview.setSource(url)


            # Reset last update time
            self.last_preview_update = 0
            
            # Start playing then immediately pause to initialize both players
            self.media_player.play()
            self.media_player_preview.play()
            self.media_player.pause()
            self.media_player_preview.pause()

            # Initial sync after a short delay to ensure both players are ready
            QTimer.singleShot(100, lambda: self._sync_preview_position(0))
            
            def on_duration_ready():
                duration = self.media_player.duration()
                if duration > 0:  # Wait until duration is valid
                    if duration < self.MIN_ZOOM_DURATION:
                        self.zoom_end = 1.0  # Show entire duration
                    else:
                        self.zoom_end = 0.2  # Show first 20%
                    # Force position update to sync timelines with new zoom
                    self.setPosition(self.media_player.position(), from_main=True)
            
            # Wait briefly for duration to be available
            QTimer.singleShot(200, on_duration_ready)
            
            self.updatePlayPauseButton()
            
    def rotateVideo(self):
        if hasattr(self, 'video_widget'):
            # Store rotation in a class variable if it doesn't exist
            if not hasattr(self, 'current_rotation'):
                self.current_rotation = 0
            
            # Update rotation
            self.current_rotation = (self.current_rotation + 90) % 360
            
            # Apply rotation using orientation
            self.video_widget.setOrientation(self.current_rotation)
            self.video_widget_preview.setOrientation(self.current_rotation)

    def updateSpeedLabel(self):
        if hasattr(self, 'media_player'):
            speed = self.media_player.playbackRate()
            self.speed_label.setText(f"{speed:.1f}x")

    def togglePlayPause(self):
        if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.media_player.pause()
            self.media_player_preview.pause()
        else:
            self.media_player.play()
            self.media_player_preview.play()
            # Sync positions when starting playback
            self._sync_preview_position(self.media_player.position())
            
    def updatePlayPauseButton(self):
        if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.play_pause_button.setText("Pause")
        else:
            self.play_pause_button.setText("Play")
            
    def setPosition(self, position, from_main=True):
        if not hasattr(self, 'media_player'):
            return
            
        duration = self.media_player.duration()
        if duration > 0:
            if from_main:
                # Direct position from main timeline
                self.media_player.setPosition(position)
            else:
                # Convert position from zoomed timeline
                zoom_duration = (self.zoom_end - self.zoom_start) * duration
                zoom_start = self.zoom_start * duration
                relative_pos = position / self.second_timeline.maximum()
                actual_position = int(zoom_start + (relative_pos * zoom_duration))
                self.media_player.setPosition(actual_position)
            
            self._sync_preview_position(self.media_player.position())
            
            # Update both timeline widgets
            self.timeline_widget.update()
            self.second_timeline_widget.update()
        
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
        self.second_timeline.setRange(0, duration)
        
        # Set zoom_end to show 20% of the slider's range
        if duration > self.MIN_ZOOM_DURATION:
            visible_range = duration / 5  # 20% of total duration
            self.zoom_end = visible_range / duration
            # Update both timelines with new zoom
            self.timeline_widget.update()
            self.second_timeline_widget.update()

    def saveAnnotations(self):
        from zipfile import ZipFile
        import csv
        import io

        filename, _ = QFileDialog.getSaveFileName(self, "Export Annotations", "", "ZIP Files (*.zip)")
        if filename:
            try:
                with ZipFile(filename, 'w') as zipf:
                    # Save labels.json
                    annotations_data = {
                        "annotations": [],
                        "videohash": self.video_hash
                    }
                    
                    for annotation in self.annotations:
                        annotations_data["annotations"].append({
                            "id": annotation.id,
                            "range": {
                                "start": annotation.start_time,
                                "end": annotation.end_time
                            },
                            "shape": annotation.shape,
                            "comments": annotation.comments
                        })
                    
                    zipf.writestr('labels.json', json.dumps(annotations_data, indent=4))

                    # Create CSV files for each heading
                    headers = {
                        'posture.csv': [],
                        'high_level_behavior.csv': [],
                        'pa_type.csv': [],
                        'behavioral_parameters.csv': [],
                        'experimental_situation.csv': []
                    }

                    for annotation in self.annotations:
                        try:
                            comment_data = json.loads(annotation.comments[0]["body"])
                            for item in comment_data:
                                selected_value = item["selectedValue"]
                                if isinstance(selected_value, list):
                                    values = selected_value
                                else:
                                    values = [selected_value]

                                for value in values:
                                    if value:
                                        if item["category"] == "POSTURE":
                                            headers['posture.csv'].append([
                                                annotation.start_time, annotation.end_time,
                                                value, 'human', 'posture',
                                                annotation.start_time, annotation.end_time
                                            ])
                                        elif item["category"] == "HIGH LEVEL BEHAVIOR":
                                            headers['high_level_behavior.csv'].append([
                                                annotation.start_time, annotation.end_time,
                                                value, 'human', 'hlb',
                                                annotation.start_time, annotation.end_time
                                            ])
                                        elif item["category"] == "PA TYPE":
                                            headers['pa_type.csv'].append([
                                                annotation.start_time, annotation.end_time,
                                                value, 'human', 'pa_type',
                                                annotation.start_time, annotation.end_time
                                            ])
                                        elif item["category"] == "Behavioral Parameters":
                                            headers['behavioral_parameters.csv'].append([
                                                annotation.start_time, annotation.end_time,
                                                value, 'human', 'behavioral_parameters',
                                                annotation.start_time, annotation.end_time
                                            ])
                                        elif item["category"] == "Experimental situation":
                                            headers['experimental_situation.csv'].append([
                                                annotation.start_time, annotation.end_time,
                                                value, 'human', 'experimental_situation',
                                                annotation.start_time, annotation.end_time
                                            ])
                        except Exception as e:
                            print(f"Error processing annotation {annotation.id}: {str(e)}")

                    # Write CSV files
                    csv_header = ['START_TIME','STOP_TIME','PREDICTION','SOURCE','LABELSET','VIDEO_START_TIME','VIDEO_END_TIME']
                    for filename, data in headers.items():
                        if data:  # Only create files for categories that have data
                            output = io.StringIO()
                            writer = csv.writer(output)
                            writer.writerow(csv_header)
                            writer.writerows(data)
                            zipf.writestr(filename, output.getvalue())
                            output.close()

                QMessageBox.information(self, "Success", "Annotations exported successfully")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to export annotations: {str(e)}")
    
    def loadAnnotations(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Load Annotations", "", "JSON Files (*.json)")
        if filename:
            try:
                with open(filename, 'r') as f:
                    data = json.load(f)
                
                self.annotations = []
                self.video_hash = data.get("videohash", "NA")
                
                for ann_data in data.get("annotations", []):
                    annotation = TimelineAnnotation()
                    annotation.id = ann_data["id"]
                    annotation.start_time = ann_data["range"]["start"]
                    annotation.end_time = ann_data["range"]["end"]
                    annotation.shape = ann_data["shape"]
                    annotation.comments = ann_data["comments"]
                    self.annotations.append(annotation)
                
                self.updateAnnotationTimeline()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load annotations: {str(e)}")

    def updateAnnotationTimeline(self):
        self.timeline_widget.update()

    # Delegate annotation operations to annotation_manager
    def toggleAnnotation(self):
        self.annotation_manager.toggleAnnotation()

    def editAnnotation(self):
        self.annotation_manager.editAnnotation()

    def cancelAnnotation(self):
        self.annotation_manager.cancelAnnotation()

    def deleteCurrentLabel(self):
        self.annotation_manager.deleteCurrentLabel()

    def moveToPreviousLabel(self):
        self.annotation_manager.moveToPreviousLabel()

    def moveToNextLabel(self):
        self.annotation_manager.moveToNextLabel()

    def mergeWithPrevious(self):
        self.annotation_manager.mergeWithPrevious()

    def mergeWithNext(self):
        self.annotation_manager.mergeWithNext()

    def splitCurrentLabel(self):
        self.annotation_manager.splitCurrentLabel()

    def keyPressEvent(self, event: QKeyEvent):
        # Handle number keys for category selection (1-5)
        if event.key() >= Qt.Key.Key_1 and event.key() <= Qt.Key.Key_5:
            # Only process if annotation dialog is active
            dialog = self.findChild(AnnotationDialog)
            if dialog:
                index = event.key() - Qt.Key.Key_1  # Convert key to 0-based index
                dialog.selectCategoryByIndex(index)
        super().keyPressEvent(event)
