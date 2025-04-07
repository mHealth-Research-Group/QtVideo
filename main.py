import sys
from PyQt6.QtWidgets import QApplication
from src.video_player import VideoPlayerApp

if __name__ == "__main__":
    app = QApplication(sys.argv)
    player = VideoPlayerApp()
    player.show()
    sys.exit(app.exec())
