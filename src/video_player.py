import json
import io
import csv
from zipfile import ZipFile
import os
import sys
from collections import OrderedDict
import uuid
from functools import partial

from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QFileDialog, QLabel, QMessageBox,
                             QMenu, QScrollArea, QGroupBox, QLineEdit)
from PyQt6.QtCore import Qt, QUrl, QTime, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QPalette, QGuiApplication
from PyQt6.QtQuickWidgets import QQuickWidget
from src.slider import CustomSlider
from src.models import TimelineAnnotation
from src.widgets import TimelineWidget
from src.dialogs import AnnotationDialog
from src.shortcuts import ShortcutManager
from src.annotation_manager import AnnotationManager
from src.utils import AutosaveManager

class VideoPlayerApp(QMainWindow):
    SYNC_THRESHOLD = 150
    MIN_ZOOM_DURATION = 600000
    BASE_PREVIEW_OFFSET = 2000

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Video Annotator")
        screen = QGuiApplication.primaryScreen()
        if screen:
            available_geometry = screen.availableGeometry()
            self.resize(int(available_geometry.width() * 0.85), int(available_geometry.height() * 0.80))
            self.move(available_geometry.center() - self.rect().center())
        else:
            self.setGeometry(100, 100, 1280, 900)

        self.autosave_manager = AutosaveManager(60000)
        self.current_video_path = None
        self.video_hash = 0
        self.current_rotation = 0
        self.annotation_sets = OrderedDict()
        self.active_timeline_key = None
        self.timeline_widgets = {}
        self.current_annotation = None
        self.zoom_start = 0.0
        self.zoom_end = 1.0
        self._is_navigating = False
        self.PREVIEW_OFFSET = self.BASE_PREVIEW_OFFSET

        self.autosave_timer = QTimer(self)
        self.autosave_timer.setInterval(self.autosave_manager.interval)
        self.autosave_timer.timeout.connect(self.autosave)

        self.setStyleSheet("""
            QMainWindow { background-color: #2b2b2b; color: #ffffff; }
            QLabel { color: #ffffff; font-size: 12px; }
            QLineEdit {
                color: #ffffff;
                background-color: transparent;
                border: none;
                padding: 2px;
            }
            QLineEdit:focus {
                background-color: #1e1e1e;
                border: 1px solid #4a90e2;
            }
            QGroupBox {
                background-color: #2b2b2b;
                border: 1px solid #3a3a3a;
                border-radius: 6px;
                margin-top: 10px;
                font-weight: bold;
                color: #cccccc;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 5px 0 5px;
            }
            QScrollArea { border: none; }
        """)

        self.qml_root_main = None
        self.qml_root_preview = None
        self._qml_main_ready = False
        self._qml_preview_ready = False
        self._pending_source_url = None

        self.media_player = {
            '_playback_state': 0,
            '_duration': 0,
            '_position': 0,
            '_playback_rate': 1.0,
        }

        self.setupUI()

        if hasattr(self, 'quick_widget_main'):
            self.quick_widget_main.statusChanged.connect(self.onQmlMainStatusChanged)
            self.onQmlMainStatusChanged(self.quick_widget_main.status())

        if hasattr(self, 'quick_widget_preview'):
            self.quick_widget_preview.statusChanged.connect(self.onQmlPreviewStatusChanged)
            self.onQmlPreviewStatusChanged(self.quick_widget_preview.status())

        self.loadQmlSources()

        self.annotation_manager = AnnotationManager(self)
        self.shortcut_manager = ShortcutManager(self)

        self.checkQmlReadyAndLoadPending()

    def setupUI(self):
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        self.main_layout = QVBoxLayout(central_widget)
        self.main_layout.setSpacing(10)

        video_container = QWidget()
        video_container.setStyleSheet("QWidget { background-color: #1a1a1a; border: 2px solid #3a3a3a; border-radius: 8px; margin: 10px; }")
        video_container.setMinimumHeight(350)
        video_container_layout = QHBoxLayout(video_container)
        video_container_layout.setContentsMargins(10, 10, 10, 10); video_container_layout.setSpacing(10)

        left_video_container = QWidget(); left_video_layout = QVBoxLayout(left_video_container); left_video_layout.setContentsMargins(0, 0, 0, 0)
        self.quick_widget_main = QQuickWidget(self)
        self.quick_widget_main.setResizeMode(QQuickWidget.ResizeMode.SizeRootObjectToView)
        self.quick_widget_main.setAttribute(Qt.WidgetAttribute.WA_AlwaysStackOnTop, False)
        self.quick_widget_main.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        palette_main = self.quick_widget_main.palette()
        palette_main.setColor(QPalette.ColorRole.Window, Qt.GlobalColor.black)
        self.quick_widget_main.setPalette(palette_main)
        self.quick_widget_main.setAutoFillBackground(True)
        left_video_layout.addWidget(self.quick_widget_main)

        right_video_container = QWidget();
        right_video_layout = QVBoxLayout(right_video_container);
        right_video_layout.setContentsMargins(0, 0, 0, 0)
        self.quick_widget_preview = QQuickWidget(self)
        self.quick_widget_preview.setResizeMode(QQuickWidget.ResizeMode.SizeRootObjectToView)
        self.quick_widget_preview.setAttribute(Qt.WidgetAttribute.WA_AlwaysStackOnTop, False)
        self.quick_widget_preview.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        palette_preview = self.quick_widget_preview.palette()
        palette_preview.setColor(QPalette.ColorRole.Window, Qt.GlobalColor.black)
        self.quick_widget_preview.setPalette(palette_preview)
        self.quick_widget_preview.setAutoFillBackground(True)
        right_video_layout.addWidget(self.quick_widget_preview)

        video_container_layout.addWidget(left_video_container)
        video_container_layout.addWidget(right_video_container)
        self.main_layout.addWidget(video_container, stretch=2)

        self.timeline_popout_window = QWidget(self, Qt.WindowType.Window)
        self.timeline_popout_window.setWindowTitle("Annotation Timelines")
        self.timeline_popout_window.setLayout(QVBoxLayout())
        self.timeline_popout_window.setGeometry(self.geometry().x() + 50, self.geometry().y() + 50, 800, 300)
        self.timeline_popout_window.closeEvent = self.dock_timelines_on_close

        self.timelines_groupbox = QGroupBox("Annotation Timelines")
        timelines_groupbox_layout = QVBoxLayout(self.timelines_groupbox)
        
        self.timelines_scroll_area = QScrollArea()
        self.timelines_scroll_area.setWidgetResizable(True)
        self.timelines_scroll_area.setMaximumHeight(250)
        self.timelines_container_widget = QWidget()
        self.timelines_layout = QVBoxLayout(self.timelines_container_widget)
        self.timelines_layout.setContentsMargins(0, 5, 0, 5)
        self.timelines_layout.setSpacing(5)
        self.timelines_scroll_area.setWidget(self.timelines_container_widget)
        timelines_groupbox_layout.addWidget(self.timelines_scroll_area)
        self.main_layout.addWidget(self.timelines_groupbox, stretch=1)
        self.docked_widget_index = self.main_layout.indexOf(self.timelines_groupbox)

        playback_controls_groupbox = QGroupBox("Timeline Controls")
        main_controls_layout = QVBoxLayout(playback_controls_groupbox)
        main_controls_layout.setSpacing(8)
        main_controls_layout.setContentsMargins(12, 12, 12, 12)

        self.overview_timeline_widget = TimelineWidget(self, show_position=False, is_main_timeline=True, draw_zoom_handles=True, key="overview", annotations_list=[])
        main_controls_layout.addWidget(self.overview_timeline_widget)
        
        self.timeline = CustomSlider(Qt.Orientation.Horizontal, show_handle=True)
        self.timeline.sliderMoved.connect(lambda pos: self.setPosition(pos, from_main=True))
        self.timeline.sliderPressed.connect(self.sliderPressed)
        self.timeline.sliderReleased.connect(self.sliderReleased)
        self.timeline.setEnabled(False)
        main_controls_layout.addWidget(self.timeline)

        self.second_timeline_widget = TimelineWidget(self, show_position=True, is_main_timeline=False, key="zoom", annotations_list=[])
        self.second_timeline = CustomSlider(Qt.Orientation.Horizontal, show_handle=False)
        self.second_timeline.sliderMoved.connect(lambda pos: self.setPosition(pos, from_main=False))
        self.second_timeline.sliderPressed.connect(self.sliderPressed)
        self.second_timeline.sliderReleased.connect(self.sliderReleased)
        self.second_timeline.setEnabled(False)
        self.time_label = QLabel("00:00:00 / 00:00:00")
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_controls_layout.addWidget(self.second_timeline_widget)
        main_controls_layout.addWidget(self.second_timeline)
        main_controls_layout.addWidget(self.time_label)
        self.main_layout.addWidget(playback_controls_groupbox)
        
        self.add_new_timeline()
        
        self.shortcuts_container = QWidget()
        self.shortcuts_container.setStyleSheet("""
            QWidget {
                background-color: #1a1a1a;
                border: 1px solid #3a3a3a;
                border-radius: 8px;
                padding: 5px;
                margin: 1px;
            }
            QLabel[isHeader="true"] {
                color: #4a90e2;
                font-size: 14px;
                font-weight: bold;
                border-bottom: 2px solid #4a90e2;
            }
            QLabel[isShortcut="true"] {
                background-color: #2a2a2a;
                border-radius: 4px;
                padding: 2px 6px;
            }
            QWidget[isColumn="true"] {
                background-color: #222222;
                border-radius: 6px;
            }
        """)
        shortcuts_layout = QHBoxLayout(self.shortcuts_container)
        shortcuts_layout.setSpacing(15)
        self._populate_shortcuts(shortcuts_layout)
        self.main_layout.addWidget(self.shortcuts_container, stretch=0)

        controls_container = QWidget()
        controls_container.setStyleSheet("""
            QWidget { background-color: #1a1a1a; border: 1px solid #3a3a3a; border-radius: 6px; margin: 8px; }
            QPushButton { padding: 8px 16px; background-color: #4a90e2; color: white; border: none; border-radius: 4px; min-width: 100px; }
            QPushButton:hover { background-color: #357abd; } QPushButton:pressed { background-color: #2a5f9e; }
            QPushButton:disabled { background-color: #555; color: #999; }
        """)
        controls_layout = QHBoxLayout(controls_container); controls_layout.setSpacing(10);
        controls_layout.setContentsMargins(12, 8, 12, 8)

        left_controls = QWidget(); left_layout = QHBoxLayout(left_controls);
        left_layout.setSpacing(10); left_layout.setContentsMargins(0, 0, 0, 0)
        self.play_pause_button = QPushButton("Play")
        self.play_pause_button.setToolTip("Play/Pause the video (Spacebar)")
        self.play_pause_button.setEnabled(False)

        self.speed_label = QLabel("1.0x")
        self.speed_label.setStyleSheet("QLabel { color: white; padding: 8px; background-color: #2a2a2a; border-radius: 4px; min-width: 50px; text-align: center; }")
        self.speed_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.preview_offset_label = QLabel(f"Skip: {self.PREVIEW_OFFSET}ms")
        self.preview_offset_label.setStyleSheet("QLabel { color: white; padding: 8px; background-color: #2a2a2a; border-radius: 4px; text-align: center; }")
        self.preview_offset_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        left_layout.addWidget(self.play_pause_button)
        left_layout.addWidget(self.speed_label)
        left_layout.addWidget(self.preview_offset_label)

        right_controls = QWidget(); right_layout = QHBoxLayout(right_controls); right_layout.setSpacing(10); right_layout.setContentsMargins(0, 0, 0, 0)
        self.open_button = QPushButton("Open Video"); self.open_button.setToolTip("Open a video file for annotation")
        self.popout_button = QPushButton("Pop Out Timelines"); self.popout_button.clicked.connect(self.toggle_timeline_popout)
        self.gear_button = QPushButton("⚙")
        self.gear_button.setToolTip("Settings")
        self.gear_button.setStyleSheet("""
            QPushButton { padding: 8px 12px; background-color: #4a90e2; color: white; border: none; border-radius: 4px; font-size: 16px; min-width: 40px; }
            QPushButton:hover { background-color: #357abd; } QPushButton:pressed { background-color: #2a5f9e; }
            QPushButton::menu-indicator { width: 0px; }
        """)
        right_layout.addWidget(self.open_button); right_layout.addWidget(self.popout_button); right_layout.addWidget(self.gear_button)
        controls_layout.addWidget(left_controls); controls_layout.addStretch(); controls_layout.addWidget(right_controls)
        self.main_layout.addWidget(controls_container)

        self.play_pause_button.clicked.connect(self.togglePlayPause)
        self.open_button.clicked.connect(self.openFile)

        self.settings_menu = QMenu(self); self.settings_menu.setStyleSheet("QMenu { background-color: #2b2b2b; border: 1px solid #3a3a3a; } QMenu::item { padding: 8px 20px; color: white; } QMenu::item:selected { background-color: #4a90e2; }")
        load_action = QAction("Load Label File(s)", self); load_action.triggered.connect(self.loadAnnotations)
        export_action = QAction("Export All Labels", self); export_action.triggered.connect(self.saveAnnotations)
        new_video_action = QAction("New Video", self); new_video_action.triggered.connect(self.openFile)
        self.rotate_action = QAction("Rotate Video", self); self.rotate_action.setEnabled(False); self.rotate_action.triggered.connect(self.rotateVideo)
        self.toggle_shortcuts_action = QAction("Hide Shortcuts", self); self.toggle_shortcuts_action.triggered.connect(self.toggleShortcutsWidget)
        self.settings_menu.addAction(load_action); self.settings_menu.addAction(export_action); self.settings_menu.addAction(new_video_action)
        self.settings_menu.addSeparator(); self.settings_menu.addAction(self.rotate_action); self.settings_menu.addSeparator()
        self.settings_menu.addAction(self.toggle_shortcuts_action)
        self.gear_button.setMenu(self.settings_menu)
    
    def toggle_timeline_popout(self):
        container = self.timelines_groupbox
        if container.parent() is self.centralWidget():
            self.main_layout.removeWidget(container)
            container.setParent(self.timeline_popout_window)
            self.timeline_popout_window.layout().addWidget(container)
            self.timeline_popout_window.show()
            self.popout_button.setEnabled(False)
        else:
            self.timeline_popout_window.layout().removeWidget(container)
            container.setParent(self.centralWidget())
            self.main_layout.insertWidget(self.docked_widget_index, container, 1)
            self.timeline_popout_window.hide()
            self.popout_button.setEnabled(True)

    def dock_timelines_on_close(self, event):
        self.toggle_timeline_popout()
        event.accept()

    def add_new_timeline(self):
        key = f"new_timeline_{uuid.uuid4().hex[:6]}"
        name = f"Default Timeline {len(self.annotation_sets) + 1}"
        self.annotation_sets[key] = {'name': name, 'annotations': []}
        self.add_timeline(key, self.annotation_sets[key], insert_at_top=False)
        return key

    def add_timeline(self, key, timeline_data, insert_at_top=False):
        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(5, 0, 5, 0)
        row_layout.setSpacing(10)

        name_edit = QLineEdit(timeline_data['name'])
        name_edit.setMinimumWidth(150)
        name_edit.setMaximumWidth(200)
        name_edit.editingFinished.connect(lambda k=key: self._on_timeline_name_changed(k))
        
        timeline_widget = TimelineWidget(self, show_position=False, is_main_timeline=True, key=key, annotations_list=timeline_data['annotations'])
        timeline_widget.activated.connect(self.set_active_timeline)
        
        remove_button = QPushButton("✖")
        remove_button.setFixedSize(24, 24)
        remove_button.setStyleSheet("QPushButton { background-color: #555; border-radius: 12px; } QPushButton:hover { background-color: #e53935; }")
        remove_button.clicked.connect(partial(self.remove_timeline, key))

        row_layout.addWidget(name_edit)
        row_layout.addWidget(timeline_widget)
        row_layout.addWidget(remove_button)

        if insert_at_top:
            self.timelines_layout.insertWidget(0, row_widget)
        else:
            self.timelines_layout.addWidget(row_widget)

        self.timeline_widgets[key] = (row_widget, timeline_widget, name_edit)
        
        if self.active_timeline_key is None:
            self.set_active_timeline(key)
        
        self.updateAnnotationTimeline()

    def _on_timeline_name_changed(self, key):
        if key in self.timeline_widgets:
            _, _, name_edit = self.timeline_widgets[key]
            new_name = name_edit.text()
            if new_name and new_name != self.annotation_sets[key]['name']:
                self.annotation_sets[key]['name'] = new_name
                self.autosave()
            else:
                name_edit.setText(self.annotation_sets[key]['name'])

    def set_active_timeline(self, key):
        if self.active_timeline_key == key:
            return
            
        self.active_timeline_key = key
        for k, (_, widget, _) in self.timeline_widgets.items():
            widget.setActive(k == key)
        
        if key in self.annotation_sets:
            active_list = self.annotation_sets[key]['annotations']
            self.overview_timeline_widget.annotations_list = active_list
            self.second_timeline_widget.annotations_list = active_list

        self.updateAnnotationTimeline()

    def remove_timeline(self, key, force=False, do_autosave=True):
        if key in self.timeline_widgets:
            if not force and len(self.timeline_widgets) <= 1:
                QMessageBox.warning(self, "Action Denied", "At least one timeline must remain.")
                return

            row_widget, _, _ = self.timeline_widgets.pop(key)
            row_widget.deleteLater()
            
            if key in self.annotation_sets:
                del self.annotation_sets[key]
            
            if self.active_timeline_key == key:
                self.active_timeline_key = None
                if self.timeline_widgets:
                    next_key = next(iter(self.timeline_widgets.keys()))
                    self.set_active_timeline(next_key)

        self.updateAnnotationTimeline()
        if do_autosave:
            self.autosave()

    def _populate_shortcuts(self, parent_layout):
        shortcut_data = {
            "🎥 Video Controls": [ "⎵ Spacebar - Play/Pause", "←/→ - Skip 10s backward/forward", "↑/↓ - Increase/decrease speed", "R - Reset speed to 1x" ],
            "🏷️ Labeling Controls": [ "A - Start/Stop labeling", "Z - Cancel labeling", "S - Delete label", "G - Open label dialog", "P - Split label" ],
            "🔍 Navigation": [ "Shift+←/→ - Previous/Next label", "N - Merge with previous", "M - Merge with next", "Shift+↑/↓ - Adjust preview skip" ],
            "📝 Dialog Controls": [ "1 - Select Posture", "2 - Select High Level Behavior", "3 - Select PA Type", "4 - Select Behavioral Parameters", "5 - Select Experimental Situation" ]
        }
        for header_text, shortcuts in shortcut_data.items():
            col_widget = QWidget(); col_widget.setProperty("isColumn", True)
            col_layout = QVBoxLayout(col_widget)
            header = QLabel(header_text); header.setProperty("isHeader", True)
            col_layout.addWidget(header)
            for sc_text in shortcuts:
                label = QLabel(sc_text); label.setProperty("isShortcut", True)
                label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
                col_layout.addWidget(label)
            col_layout.addStretch()
            parent_layout.addWidget(col_widget)

    def loadQmlSources(self):
        if getattr(sys, 'frozen', False):
            base_path = os.path.join(sys._MEIPASS, 'src')
        else:
            base_path = os.path.dirname(__file__)
        qml_file_path = os.path.join(base_path, 'VideoPlayer.qml')

        if not os.path.exists(qml_file_path):
            QMessageBox.critical(self, "QML Error", f"Cannot find QML file:\n{qml_file_path}")
            return

        if hasattr(self, 'quick_widget_main'):
            self.quick_widget_main.setSource(QUrl.fromLocalFile(qml_file_path))
        if hasattr(self, 'quick_widget_preview'):
            self.quick_widget_preview.setSource(QUrl.fromLocalFile(qml_file_path))

    def onQmlMainStatusChanged(self, status):
        is_already_ready = self._qml_main_ready
        if status == QQuickWidget.Status.Ready and is_already_ready: return
        if status == QQuickWidget.Status.Null and is_already_ready:
             self._qml_main_ready = False
             self.checkQmlReadyAndLoadPending()

        if status == QQuickWidget.Status.Ready:
            if not is_already_ready:
                self.qml_root_main = self.quick_widget_main.rootObject()
                if self.qml_root_main:
                    self._qml_main_ready = True
                    self.qml_root_main.qmlPositionChanged.connect(self.qmlPositionChanged)
                    self.qml_root_main.qmlDurationChanged.connect(self.qmlDurationChanged)
                    self.qml_root_main.qmlPlaybackStateChanged.connect(self.qmlPlaybackStateChanged)
                    self.qml_root_main.qmlMediaStatusChanged.connect(self.qmlMediaStatusChanged)
                    self.qml_root_main.qmlErrorOccurred.connect(self.qmlErrorOccurred)
                    self.qml_root_main.qmlPlaybackRateChanged.connect(self.qmlPlaybackRateChanged)
                    self.qml_root_main.setProperty('orientation', self.current_rotation)
                    self.checkQmlReadyAndLoadPending()
                else: self._qml_main_ready = False
        elif status == QQuickWidget.Status.Error:
            for error in self.quick_widget_main.errors(): print(f"    {error.toString()}")
            QMessageBox.critical(self, "QML Error", "Failed to load main video player QML component.")
            self._qml_main_ready = False

    def onQmlPreviewStatusChanged(self, status):
        is_already_ready = self._qml_preview_ready
        if status == QQuickWidget.Status.Ready and is_already_ready: return
        if status == QQuickWidget.Status.Null and is_already_ready:
            self._qml_preview_ready = False
            self.checkQmlReadyAndLoadPending()

        if status == QQuickWidget.Status.Ready:
             if not is_already_ready:
                self.qml_root_preview = self.quick_widget_preview.rootObject()
                if self.qml_root_preview:
                    self._qml_preview_ready = True
                    self.qml_root_preview.setProperty('isPreview', True)
                    self.qml_root_preview.setProperty('orientation', self.current_rotation)
                    self.checkQmlReadyAndLoadPending()
                else: self._qml_preview_ready = False
        elif status == QQuickWidget.Status.Error:
            for error in self.quick_widget_preview.errors(): print(f"    {error.toString()}")
            QMessageBox.critical(self, "QML Error", "Failed to load preview video player QML component.")
            self._qml_preview_ready = False

    def checkQmlReadyAndLoadPending(self):
        qml_is_fully_ready = self._qml_main_ready and self._qml_preview_ready
        self.play_pause_button.setEnabled(qml_is_fully_ready and self.media_player['_duration'] > 0)
        self.rotate_action.setEnabled(qml_is_fully_ready)
        self.timeline.setEnabled(qml_is_fully_ready and self.media_player['_duration'] > 0)
        self.second_timeline.setEnabled(qml_is_fully_ready and self.media_player['_duration'] > 0)

        if qml_is_fully_ready:
            if self._pending_source_url:
                url_to_load = self._pending_source_url
                self._pending_source_url = None
                self.setQmlSource(url_to_load)
            else: self._update_ui_from_state()

    def setQmlSource(self, source_url: QUrl):
         if not (self.qml_root_main and self.qml_root_preview):
              self._pending_source_url = source_url
              return
         self.media_player['_duration'] = 0
         self.media_player['_position'] = 0
         self.media_player['_playback_state'] = 0
         self.media_player['_playback_rate'] = 1.0
         self._update_ui_from_state()
         self.qml_root_main.setProperty('source', source_url)
         self.qml_root_preview.setProperty('source', source_url)
         self.play_pause_button.setEnabled(False)
         self.timeline.setEnabled(False)
         self.second_timeline.setEnabled(False)

    def qmlPositionChanged(self, position):
        self.media_player['_position'] = int(position)
        if not self.timeline.isSliderDown():
             self.timeline.setValue(self.media_player['_position'])
        if not self.second_timeline.isSliderDown() and self.media_player['_duration'] > 0:
            zoom_duration = (self.zoom_end - self.zoom_start) * self.media_player['_duration']
            zoom_start = self.zoom_start * self.media_player['_duration']
            max_slider_val = self.second_timeline.maximum()
            if position >= zoom_start and position <= (zoom_start + zoom_duration) and zoom_duration > 0 and max_slider_val > 0:
                relative_pos_in_zoom = (position - zoom_start) / zoom_duration
                slider_value = int(relative_pos_in_zoom * max_slider_val)
                self.second_timeline.setValue(slider_value)
            elif position < zoom_start: self.second_timeline.setValue(0)
            else: self.second_timeline.setValue(max_slider_val)

        current_time = QTime(0, 0).addMSecs(self.media_player['_position']).toString('hh:mm:ss')
        total_time = QTime(0, 0).addMSecs(self.media_player['_duration']).toString('hh:mm:ss')
        self.time_label.setText(f"{current_time} / {total_time}")
        self.updateAnnotationTimeline()

    def qmlDurationChanged(self, duration):
        new_duration = int(duration)
        if new_duration != self.media_player['_duration']:
            self.media_player['_duration'] = new_duration
            has_duration = self.media_player['_duration'] > 0
            self.timeline.setRange(0, self.media_player['_duration'] if has_duration else 0)
            self.second_timeline.setRange(0, self.media_player['_duration'] if has_duration else 0)
            self.timeline.setEnabled(has_duration)
            self.second_timeline.setEnabled(has_duration)
            if has_duration:
                self._setup_timeline_zoom()
                current_time = QTime(0, 0).addMSecs(self.media_player['_position']).toString('hh:mm:ss')
                total_time = QTime(0, 0).addMSecs(self.media_player['_duration']).toString('hh:mm:ss')
                self.time_label.setText(f"{current_time} / {total_time}")
            else:
                self.time_label.setText("00:00:00 / 00:00:00")
            self.updateAnnotationTimeline()

    def qmlPlaybackStateChanged(self, state):
        if state != self.media_player['_playback_state']:
             self.media_player['_playback_state'] = state
             self.updatePlayPauseButton(state)

    def _calculate_preview_offset(self):
        return int(self.BASE_PREVIEW_OFFSET * self.media_player['_playback_rate'])

    def qmlPlaybackRateChanged(self, rate):
        if rate != self.media_player['_playback_rate']:
             self.media_player['_playback_rate'] = rate
             self.updateSpeedLabel(rate)
             self.PREVIEW_OFFSET = self._calculate_preview_offset()
             self._sync_preview_qml_position(self.media_player['_position'])
             self.preview_offset_label.setText(f"Skip: {self.PREVIEW_OFFSET}ms")

    def qmlMediaStatusChanged(self, status):
        media_is_ready = (status == 2 or status == 3)
        media_is_invalid = (status == 7)

        if media_is_ready:
             if self.media_player['_duration'] == 0:
                 self._setup_timeline_zoom()
             self.qmlDurationChanged(self.qml_root_main.property('duration'))
             self.qmlPositionChanged(self.qml_root_main.property('position'))
             self.play_pause_button.setEnabled(True)
        elif media_is_invalid:
             error_str = self.qml_root_main.property('errorString') if self.qml_root_main else "Unknown error"
             QMessageBox.critical(self, "Media Error", f"QML MediaPlayer reported Invalid Media.\nError: {error_str}")
             self.current_video_path = None
             if self.autosave_timer.isActive(): self.autosave_timer.stop()
             self.play_pause_button.setEnabled(False)
             self.timeline.setEnabled(False)
             self.second_timeline.setEnabled(False)

    def qmlErrorOccurred(self, error, errorString):
        if error != 0:
            QMessageBox.critical(self, "QML Playback Error", f"Error: {errorString} (Code: {error})")
            self.play_pause_button.setEnabled(False)
            self.timeline.setEnabled(False)
            self.second_timeline.setEnabled(False)

    def _update_ui_from_state(self):
         self.updatePlayPauseButton(self.media_player['_playback_state'])
         self.updateSpeedLabel(self.media_player['_playback_rate'])
         self.qmlDurationChanged(self.media_player['_duration'])
         self.qmlPositionChanged(self.media_player['_position'])

    def openFile(self):
        self.current_rotation = 0
        if self._qml_main_ready: self.qml_root_main.setProperty('orientation', 0)
        if self._qml_preview_ready: self.qml_root_preview.setProperty('orientation', 0)

        filename, _ = QFileDialog.getOpenFileName(self, "Open Video", "", "Video Files (*.mp4 *.avi *.mkv *.mov)")
        if filename:
            self.current_video_path = filename
            try: self.video_hash = self.autosave_manager.calculate_video_hash(filename)
            except Exception as e: self.video_hash = 0

            for key in list(self.timeline_widgets.keys()):
                self.remove_timeline(key, force=True, do_autosave=False)
            self.annotation_sets.clear()
            self.active_timeline_key = None
            
            autosave_data, hash_matches = self.autosave_manager.check_for_autosave(filename, self.video_hash)
            should_load_autosave = False
            if autosave_data:
                message = "An autosaved version of the annotations was found."
                if self.video_hash != 0 and not hash_matches:
                    message += "\nWarning: The video file appears to have changed since the autosave."
                message += "\nWould you like to restore from autosave or start over?"
                reply = QMessageBox.question(self, "Autosave Found", message, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.Yes)
                if reply == QMessageBox.StandardButton.Yes:
                    should_load_autosave = True
                else:
                    self.autosave_manager.delete_autosave(filename)

            if should_load_autosave:
                try:
                    timeline_order = autosave_data.get("timeline_order", list(autosave_data.get("annotation_sets", {}).keys()))
                    for key in timeline_order:
                        if key not in autosave_data.get("annotation_sets", {}): continue
                        timeline_data = autosave_data["annotation_sets"][key]
                        loaded_annotations = []
                        for ann_data in timeline_data.get('annotations', []):
                            if "range" in ann_data and "start" in ann_data["range"] and "end" in ann_data["range"]:
                                 annotation = TimelineAnnotation()
                                 annotation.id = ann_data.get("id", str(uuid.uuid4()))
                                 annotation.start_time = ann_data["range"]["start"]
                                 annotation.end_time = ann_data["range"]["end"]
                                 annotation.shape = ann_data.get("shape", {})
                                 annotation.comments = ann_data.get("comments", [])
                                 if not annotation.comments:
                                     annotation._add_initial_comment()
                                 loaded_annotations.append(annotation)
                        
                        timeline_name = timeline_data.get('name', key)
                        self.annotation_sets[key] = {'name': timeline_name, 'annotations': loaded_annotations}
                        self.add_timeline(key, self.annotation_sets[key], insert_at_top=False)
                except Exception as e:
                    QMessageBox.critical(self, "Autosave Error", f"Failed to load autosave: {e}")
                    self.annotation_sets.clear()
            
            if not self.annotation_sets:
                self.add_new_timeline()
            
            self.updateAnnotationTimeline()

            if getattr(sys, 'frozen', False):
                from urllib.parse import quote
                filename_quoted = quote(filename)
                if not filename_quoted.startswith('/'): filename_quoted = '/' + filename_quoted
                url = QUrl('file://' + filename_quoted)
            else: url = QUrl.fromLocalFile(filename)

            if not url.isValid():
                QMessageBox.critical(self, "File Error", f"Invalid file URL generated:\n{url.toString()}")
                return

            if self._qml_main_ready and self._qml_preview_ready:
                 self.setQmlSource(url)
            else: self._pending_source_url = url

            if not self.autosave_timer.isActive():
                self.autosave_timer.start()

    def togglePlayPause(self):
        if not self.qml_root_main or not self.current_video_path: return
        if self.media_player['_playback_state'] == 1:
            self.qml_root_main.pause()
            self.qml_root_preview.pause()
        else:
            self._sync_preview_qml_position(self.media_player['_position'])
            self.qml_root_main.play()
            self.qml_root_preview.play()

    def updatePlayPauseButton(self, state):
        self.play_pause_button.setText("Pause" if state == 1 else "Play")
        media_has_duration = self.media_player['_duration'] > 0
        qml_ready = self._qml_main_ready and self._qml_preview_ready
        self.play_pause_button.setEnabled(media_has_duration and qml_ready)

    def adjustPreviewOffset(self, offset):
        base_offset_change = offset / self.media_player['_playback_rate'] if self.media_player['_playback_rate'] != 0 else 0
        self.BASE_PREVIEW_OFFSET = max(0, self.BASE_PREVIEW_OFFSET + base_offset_change)
        self.PREVIEW_OFFSET = self._calculate_preview_offset()
        if self.qml_root_preview:
            self._sync_preview_qml_position(self.media_player['_position'])
            self.preview_offset_label.setText(f"Skip: {self.PREVIEW_OFFSET}ms")

    def updateSpeedLabel(self, rate): self.speed_label.setText(f"{rate:.1f}x")

    def setPlaybackRate(self, rate):
        if self.qml_root_main and self.qml_root_preview:
             clamped_rate = max(0.1, min(rate, 16.0))
             if clamped_rate != self.media_player['_playback_rate']:
                 self.qml_root_main.setProperty('playbackRate', clamped_rate)
                 self.qml_root_preview.setProperty('playbackRate', clamped_rate)
                 self.updateSpeedLabel(clamped_rate)
                 self.PREVIEW_OFFSET = self._calculate_preview_offset()
                 self._sync_preview_qml_position(self.media_player['_position'])

    def changePlaybackRate(self, delta): self.setPlaybackRate(self.media_player['_playback_rate'] + delta)
    def resetPlaybackRate(self): self.setPlaybackRate(1.0)

    def setPosition(self, position, from_main=True):
        if not self.qml_root_main or not self.current_video_path: return
        if from_main: target_position = position
        else:
            zoom_duration = (self.zoom_end - self.zoom_start) * self.media_player['_duration']
            zoom_start = self.zoom_start * self.media_player['_duration']
            max_slider_val = self.second_timeline.maximum()
            relative_pos_in_zoom = position / max_slider_val if max_slider_val > 0 else 0
            target_position = int(zoom_start + (relative_pos_in_zoom * zoom_duration))

        self.qml_root_main.seek(target_position)
        self.qml_root_preview.seek(target_position + self.PREVIEW_OFFSET)
        self.media_player['_position'] = target_position
        self.timeline.setValue(target_position)

        if self.media_player['_duration'] > 0:
            zoom_duration = (self.zoom_end - self.zoom_start) * self.media_player['_duration']
            zoom_start = self.zoom_start * self.media_player['_duration']
            if target_position >= zoom_start and target_position <= (zoom_start + zoom_duration):
                relative_pos = (target_position - zoom_start) / zoom_duration
                self.second_timeline.setValue(int(relative_pos * self.second_timeline.maximum()))
            elif target_position < zoom_start: self.second_timeline.setValue(0)
            else: self.second_timeline.setValue(self.second_timeline.maximum())

    def _setup_timeline_zoom(self):
         if self.media_player['_duration'] <= 0: return
         if self.media_player['_duration'] < self.MIN_ZOOM_DURATION:
             self.zoom_start = 0.0; self.zoom_end = 1.0
         else: self.zoom_start = 0.0; self.zoom_end = 0.2
         
    def updateAnnotationTimeline(self):
        self.overview_timeline_widget.update()
        self.second_timeline_widget.update()
        for _, widget, _ in self.timeline_widgets.values():
            widget.update()

    def _sync_preview_qml_position(self, main_position):
        if not self.qml_root_preview or self.media_player['_duration'] <= 0: return
        target_preview_pos = main_position + self.PREVIEW_OFFSET if not self._is_navigating else main_position
        target_preview_pos = max(0, min(target_preview_pos, self.media_player['_duration']))
        current_preview_pos = self.qml_root_preview.property('position')
        is_seeking = self.timeline.isSliderDown() or self.second_timeline.isSliderDown()
        if abs(target_preview_pos - current_preview_pos) > self.SYNC_THRESHOLD or is_seeking or self._is_navigating:
            self.qml_root_preview.seek(target_preview_pos)

    def saveAnnotations(self):
        if not self.annotation_sets:
            QMessageBox.information(self, "Export", "There are no labels to export.")
            return
            
        filename, _ = QFileDialog.getSaveFileName(self, "Export All Annotations", "", "ZIP Files (*.zip)")
        if not filename: return
            
        try:
            with ZipFile(filename, 'w') as zipf:
                for key, data in self.annotation_sets.items():
                    annotations = data['annotations']
                    sanitized_key = "".join(c for c in data['name'] if c.isalnum() or c in (' ', '.', '_')).rstrip()
                    
                    json_data = { "annotations": [], "videohash": self.video_hash }
                    for ann in annotations:
                        json_data["annotations"].append({
                            "id": ann.id, "range": {"start": ann.start_time, "end": ann.end_time},
                            "shape": ann.shape, "comments": ann.comments
                        })
                    zipf.writestr(f'labels_{sanitized_key}.json', json.dumps(json_data, indent=4))
                    
                    csv_headers = ['START_TIME','STOP_TIME','PREDICTION','SOURCE','LABELSET','VIDEO_START_TIME','VIDEO_END_TIME']
                    from collections import defaultdict
                    csv_data = defaultdict(list)
                    
                    for ann in annotations:
                        try:
                            comment_data = json.loads(ann.comments[0]["body"])
                            cat_map = {
                                "POSTURE": "posture", "HIGH LEVEL BEHAVIOR": "high_level_behavior",
                                "PA TYPE": "pa_type", "Behavioral Parameters": "behavioral_parameters",
                                "Experimental situation": "experimental_situation"
                            }
                            for item in comment_data:
                                category = item.get("category")
                                if category in cat_map:
                                    values = item.get("selectedValue")
                                    if not isinstance(values, list): values = [values]
                                    for value in values:
                                        if value:
                                            csv_data[f"{cat_map[category]}_{sanitized_key}.csv"].append([
                                                ann.start_time, ann.end_time, value, 'human', cat_map[category],
                                                ann.start_time, ann.end_time
                                            ])
                        except Exception: continue
                        
                    for csv_filename, data_rows in csv_data.items():
                        if data_rows:
                            output = io.StringIO()
                            writer = csv.writer(output)
                            writer.writerow(csv_headers)
                            writer.writerows(data_rows)
                            zipf.writestr(csv_filename, output.getvalue())
            QMessageBox.information(self, "Success", "All annotations exported successfully.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to export annotations: {e}")

    def autosave(self):
        if hasattr(self, 'current_video_path') and self.current_video_path:
            self.autosave_manager.save_annotations(
                self.current_video_path, self.annotation_sets, video_hash=self.video_hash
            )

    def rotateVideo(self):
        if not self.qml_root_main or not self.qml_root_preview: return
        self.current_rotation = (self.current_rotation + 90) % 360
        self.qml_root_main.setProperty('orientation', self.current_rotation)
        self.qml_root_preview.setProperty('orientation', self.current_rotation)

    def toggleShortcutsWidget(self):
        if hasattr(self, 'shortcuts_container'):
            self.shortcuts_container.setVisible(not self.shortcuts_container.isVisible())

    def loadAnnotations(self):
        filenames, _ = QFileDialog.getOpenFileNames(self, "Load Annotation Files", "", "JSON Files (*.json)")
        if not filenames: return
        
        for filename in filenames:
            try:
                with open(filename, 'r') as f: data = json.load(f)

                if self.current_video_path:
                    saved_hash = data.get("videohash", 0)
                    if saved_hash != self.video_hash:
                        reply = QMessageBox.question(self, "Hash Mismatch",
                            f"The annotations in '{os.path.basename(filename)}' may not match the current video.\nContinue loading anyway?",
                            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                        if reply == QMessageBox.StandardButton.No: continue
                
                new_annotations = []
                for ann_data in data.get("annotations", []):
                    annotation = TimelineAnnotation()
                    annotation.id = ann_data.get("id", str(uuid.uuid4()))
                    annotation.start_time = ann_data["range"]["start"]
                    annotation.end_time = ann_data["range"]["end"]
                    annotation.shape = ann_data.get("shape", {})
                    annotation.comments = ann_data.get("comments", [])
                    if not annotation.comments:
                        annotation._add_initial_comment()
                    new_annotations.append(annotation)
                
                key = f"file_{uuid.uuid4().hex[:6]}"
                name = os.path.basename(filename)
                self.annotation_sets[key] = {'name': name, 'annotations': new_annotations}
                self.add_timeline(key, self.annotation_sets[key], insert_at_top=True)

            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load '{os.path.basename(filename)}':\n{e}")
        
        self.updateAnnotationTimeline()
        self.autosave()

    def sliderPressed(self): pass
    def sliderReleased(self): pass

    def toggleAnnotation(self): self.annotation_manager.toggleAnnotation(self.active_timeline_key)
    def editAnnotation(self):
        if self.media_player and self.media_player['_playback_state'] == 1:
            self.play_pause_button.click()
        self.annotation_manager.editAnnotation(self.active_timeline_key)
    def cancelAnnotation(self): self.annotation_manager.cancelAnnotation(self.active_timeline_key)
    def deleteCurrentLabel(self): self.annotation_manager.deleteCurrentLabel(self.active_timeline_key)
    def moveToPreviousLabel(self):
        self._is_navigating = True
        self.annotation_manager.moveToPreviousLabel(self.active_timeline_key)
        QTimer.singleShot(100, lambda: setattr(self, '_is_navigating', False))
    def moveToNextLabel(self):
        self._is_navigating = True
        self.annotation_manager.moveToNextLabel(self.active_timeline_key)
        QTimer.singleShot(100, lambda: setattr(self, '_is_navigating', False))
    def mergeWithPrevious(self): self.annotation_manager.mergeWithPrevious(self.active_timeline_key)
    def mergeWithNext(self): self.annotation_manager.mergeWithNext(self.active_timeline_key)
    def splitCurrentLabel(self): self.annotation_manager.splitCurrentLabel(self.active_timeline_key)