# main.py

import sys
import os
from PyQt6.QtWidgets import QApplication

# Ensure the 'src' directory is in the Python path
# This allows importing modules from src like 'from src.video_player import VideoPlayerApp'
script_dir = os.path.dirname(__file__)
src_dir = os.path.join(script_dir, 'src')
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

try:
    # Import the main application class from the src directory
    from src.video_player import VideoPlayerApp
except ImportError as e:
     print(f"Error importing VideoPlayerApp: {e}", file=sys.stderr)
     print("Please ensure 'src' directory exists and contains 'video_player.py'", file=sys.stderr)
     print("Also check dependencies like PyQt6.", file=sys.stderr)
     sys.exit(1)

if __name__ == '__main__':
    # Check for the essential QML file
    qml_file = 'VideoPlayer.qml'
    # Assume QML file is inside the src directory alongside video_player.py
    qml_file_path = os.path.join(src_dir, qml_file)

    if not os.path.exists(qml_file_path):
         print(f"ERROR: {qml_file} not found in src directory: {src_dir}", file=sys.stderr)
         print("Video playback requires this QML file.", file=sys.stderr)
         # Attempt to create a dummy file for UI testing only
         try:
             with open(qml_file_path, 'w') as f:
                 f.write("import QtQuick 6.2\nRectangle { width: 100; height: 100; color:'red'; Text { anchors.centerIn: parent; text: 'VideoPlayer.qml Missing!' } }")
             print(f"Created dummy {qml_file_path}. Replace with correct content for video.", file=sys.stderr)
         except Exception as e:
             print(f"Could not create dummy QML file: {e}", file=sys.stderr)
             sys.exit(1)

    # Set environment variable for verbose logging if needed for debugging
    # os.environ['QT_LOGGING_RULES'] = 'qt.multimedia.*=true;qt.qml.*=true;qt.quickwidget.*=true'
    # os.environ['QSG_RENDER_LOOP'] = 'basic' # Try software rendering if issues occur

    app = QApplication(sys.argv)
    player = VideoPlayerApp()
    player.show()
    print("--- Application Started ---")
    sys.exit(app.exec())