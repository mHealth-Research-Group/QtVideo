from PyQt6.QtGui import QAction

class ShortcutManager:
    def __init__(self, app):
        self.app = app
        self.setupShortcuts()
        
    def setupShortcuts(self):
        # Video control shortcuts
        self.spacebar_shortcut = QAction("Play/Pause", self.app)
        self.spacebar_shortcut.setShortcut("Space")
        self.spacebar_shortcut.triggered.connect(self.app.togglePlayPause)
        self.app.addAction(self.spacebar_shortcut)

        # Frame rate controls
        self.reset_rate = QAction("Reset Frame Rate", self.app)
        self.reset_rate.setShortcut("r")
        self.reset_rate.triggered.connect(lambda: self.setPlaybackRate(1.0))
        self.app.addAction(self.reset_rate)

        self.increase_rate = QAction("Increase Frame Rate", self.app)
        self.increase_rate.setShortcut("Up")
        self.increase_rate.triggered.connect(lambda: self.adjustPlaybackRate(0.25))
        self.app.addAction(self.increase_rate)

        self.decrease_rate = QAction("Decrease Frame Rate", self.app)
        self.decrease_rate.setShortcut("Down")
        self.decrease_rate.triggered.connect(lambda: self.adjustPlaybackRate(-0.25))
        self.app.addAction(self.decrease_rate)

        # Time skip controls
        self.skip_forward = QAction("Skip Forward", self.app)
        self.skip_forward.setShortcut("Right")
        self.skip_forward.triggered.connect(lambda: self.skipTime(10000))
        self.app.addAction(self.skip_forward)

        self.skip_backward = QAction("Skip Backward", self.app)
        self.skip_backward.setShortcut("Left")
        self.skip_backward.triggered.connect(lambda: self.skipTime(-10000))
        self.app.addAction(self.skip_backward)

        # Labelling shortcuts
        self.start_label = QAction("Start/Stop Labelling", self.app)
        self.start_label.setShortcut("a")
        self.start_label.triggered.connect(self.app.toggleAnnotation)
        self.app.addAction(self.start_label)

        self.cancel_label = QAction("Cancel Labelling", self.app)
        self.cancel_label.setShortcut("z")
        self.cancel_label.triggered.connect(self.app.cancelAnnotation)
        self.app.addAction(self.cancel_label)

        self.delete_label = QAction("Delete Label", self.app)
        self.delete_label.setShortcut("s")
        self.delete_label.triggered.connect(self.app.deleteCurrentLabel)
        self.app.addAction(self.delete_label)

        # Label navigation
        self.prev_label_start = QAction("Previous Label Start", self.app)
        self.prev_label_start.setShortcut("Shift+Left")
        self.prev_label_start.triggered.connect(self.app.moveToPreviousLabel)
        self.app.addAction(self.prev_label_start)

        self.next_label_start = QAction("Next Label Start", self.app)
        self.next_label_start.setShortcut("Shift+Right")
        self.next_label_start.triggered.connect(self.app.moveToNextLabel)
        self.app.addAction(self.next_label_start)

        # Label merging
        self.merge_prev = QAction("Merge with Previous", self.app)
        self.merge_prev.setShortcut("n")
        self.merge_prev.triggered.connect(self.app.mergeWithPrevious)
        self.app.addAction(self.merge_prev)

        self.merge_next = QAction("Merge with Next", self.app)
        self.merge_next.setShortcut("m")
        self.merge_next.triggered.connect(self.app.mergeWithNext)
        self.app.addAction(self.merge_next)

        # Advanced preview controls
        self.increase_preview = QAction("Increase Preview Skip", self.app)
        self.increase_preview.setShortcut("Shift+Up")
        self.increase_preview.triggered.connect(lambda: self.adjustPreviewSkip(2))
        self.app.addAction(self.increase_preview)

        self.decrease_preview = QAction("Decrease Preview Skip", self.app)
        self.decrease_preview.setShortcut("Shift+Down")
        self.decrease_preview.triggered.connect(lambda: self.adjustPreviewSkip(-2))
        self.app.addAction(self.decrease_preview)

        # Split label
        self.split_label = QAction("Split Label", self.app)
        self.split_label.setShortcut("p")
        self.split_label.triggered.connect(self.app.splitCurrentLabel)
        self.app.addAction(self.split_label)

        # Dialog control
        self.toggle_dialog = QAction("Toggle Dialog", self.app)
        self.toggle_dialog.setShortcut("g")
        self.toggle_dialog.triggered.connect(self.app.editAnnotation)
        self.app.addAction(self.toggle_dialog)

    def setPlaybackRate(self, rate):
        """Set the playback rate directly for both players"""
        self.app.media_player.setPlaybackRate(rate)
        self.app.media_player_preview.setPlaybackRate(rate)

    def adjustPlaybackRate(self, delta):
        """Adjust the playback rate by the given delta for both players"""
        current_rate = self.app.media_player.playbackRate()
        new_rate = max(0.25, current_rate + delta)  # Ensure rate doesn't go below 0.25
        self.app.media_player.setPlaybackRate(new_rate)
        self.app.media_player_preview.setPlaybackRate(new_rate)

    def skipTime(self, ms):
        """Skip forward or backward by the specified number of milliseconds"""
        current = self.app.media_player.position()
        new_pos = max(0, min(current + ms, self.app.media_player.duration()))
        self.app.media_player.setPosition(new_pos)

    def adjustPreviewSkip(self, seconds):
        """Adjust the preview skip time"""
        current_time = self.app.media_player.position() / 1000
        # Preview the position by skipping forward/backward
        preview_time = current_time + seconds
        # Ensure preview time stays within video bounds
        preview_time = max(0, min(preview_time, self.app.media_player.duration() / 1000))
        # Set the new position
        self.app.media_player.setPosition(int(preview_time * 1000))
