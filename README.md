# PAAWS Annotation Software

A PyQt6-based video annotation tool for labeling video content with temporal annotations. Designed for physical activity and posture analysis with hierarchical category selection.

## Features

- **Dual Video Preview**: Main video player with synchronized preview window showing content ahead
- **Dual Timeline System**: Full timeline overview with detailed zoom view
- **Temporal Annotations**: Create, edit, merge, split, and delete time-based labels
- **Category-Based Labeling**: Hierarchical categories including Posture, High Level Behavior, PA Type, Behavioral Parameters, and Experimental Situation
- **Smart Label Validation**: Automatic detection of incompatible label combinations based on configurable mappings
- **Autosave**: Automatic periodic saving with video hash validation to detect file changes
- **Keyboard Shortcuts**: Comprehensive keyboard controls for efficient labeling workflow
- **Export**: Export annotations as JSON and CSV files in a ZIP archive

## Installation

### Requirements

- Python 3.11+
- PyQt6
- See `requirements.txt` for full list of dependencies

### Setup

```bash
# Clone the repository
git clone <repository-url>
cd QtVideo

# Install dependencies
pip install -r requirements.txt

# Run the application
python main.py
```

## Usage

### Basic Workflow

1. **Open Video**: Click "Open Video" or use the gear menu í "New Video"
2. **Create Annotation**: Press `A` to start labeling at current position, press `A` again to finish
3. **Edit Labels**: Press `G` to open the category selection dialog
4. **Navigate**: Use arrow keys to skip through video, or Shift+Arrow to jump between labels
5. **Export**: Use gear menu í "Export Labels" to save annotations

### Keyboard Shortcuts

#### Video Controls
- `Spacebar` - Play/Pause
- `ê/í` - Skip 10s backward/forward
- `ë/ì` - Increase/decrease playback speed
- `R` - Reset speed to 1.0x
- `Shift+ë/ì` - Adjust preview skip offset

#### Annotation Controls
- `A` - Start/Stop labeling
- `G` - Open label dialog
- `Z` - Cancel current labeling
- `S` - Delete current label
- `P` - Split label at current position

#### Navigation
- `Shift+ê/í` - Jump to previous/next label boundary
- `N` - Merge with previous label
- `M` - Merge with next label

#### Dialog Controls
- `1-5` - Quick access to category dropdowns in label dialog

## Configuration

### Categories
Edit `data/categories/categories.csv` to customize available label options for each category.

### Label Mappings
Edit `data/mapping/mapping.json` to define valid combinations between categories (e.g., which postures are compatible with which PA types).

## Building

The project includes GitHub Actions workflows for building standalone executables:

- **Windows**: Creates `PAAWS-Annotation-Software.exe`
- **macOS**: Creates `PAAWS-Annotation-Software.dmg`
- **Linux**: Creates `PAAWS-Annotation-Software` binary

To build manually with PyInstaller:

```bash
# Install PyInstaller
pip install pyinstaller

# Build (example for Windows)
pyinstaller --name "PAAWS-Annotation-Software" --windowed --onefile \
  --add-data "src/VideoPlayer.qml;src" \
  --add-data "data;data" \
  main.py
```

## Testing

```bash
# Install test dependencies
pip install -r requirements-test.txt

# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_video_player.py
```

## Development

See [CLAUDE.md](CLAUDE.md) for detailed architecture documentation and development guidelines.

## License

[Add your license information here]

## Contributors

[Add contributor information here]
