import pytest
import json
from unittest.mock import patch, MagicMock

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget, QLabel, QPushButton # Import QWidget
from src.dialogs import AnnotationDialog

@pytest.fixture
def mock_categories_csv():
    csv_content = (
        "POSTURE,HIGH LEVEL BEHAVIOR,PA TYPE,Behavioral Parameters,Experimental situation\n"
        "Standing,Walking,Approach,Fast,Baseline\n"
        "Sitting,Speaking,Avoid,Slow,Test\n"
        "Lying Down,Resting,,,"
    )
    with patch('src.dialogs.open', new=MagicMock(read_data=csv_content)) as mock_open:
        mock_open.return_value.__enter__.return_value.read.return_value = csv_content
        mock_open.return_value.__enter__.return_value.__iter__.return_value = csv_content.splitlines().__iter__()
        yield

@pytest.fixture
def mock_annotation():
    annotation = MagicMock()
    comment_data = [
        {"category": "POSTURE", "selectedValue": "Sitting"},
        {"category": "HIGH LEVEL BEHAVIOR", "selectedValue": ["Walking", "Grooming"]},
        {"category": "PA TYPE", "selectedValue": "Avoid"},
        {"category": "Behavioral Parameters", "selectedValue": ["Slow"]},
        {"category": "Experimental situation", "selectedValue": "Test"},
        {"category": "Special Notes", "selectedValue": "This is a test note."}
    ]
    annotation.comments = [{"body": json.dumps(comment_data)}]
    return annotation

class MockParentWidget(QWidget):
    def __init__(self, manager):
        super().__init__()
        self.annotation_manager = manager

@pytest.fixture
def mock_parent_with_defaults():
    manager = MagicMock()
    manager.default_labels = {
        "posture": "Standing",
        "hlb": ["Resting"],
        "pa_type": "Approach",
        "behavioral_params": ["Fast"],
        "exp_situation": "Baseline",
        "special_notes": "Default notes."
    }
    return MockParentWidget(manager)

# --- Test Cases ---

def test_dialog_initialization_empty(qtbot, mock_categories_csv):
    dialog = AnnotationDialog()
    qtbot.addWidget(dialog)
    assert dialog.posture_active.text() == "Posture_Unlabeled"
    assert dialog.hlb_active.text() == "HLB_Unlabeled"
    assert dialog.notes_edit.text() == ""
    
def test_single_selection_updates_active_label(qtbot, mock_categories_csv):
    dialog = AnnotationDialog()
    qtbot.addWidget(dialog)
    dialog.posture_selection.handle_selection("Standing")
    assert dialog.posture_active.text() == "Standing"

# This test is now fixed
def test_multi_selection_adds_and_removes_tags(qtbot, mock_categories_csv):
    dialog = AnnotationDialog()
    qtbot.addWidget(dialog)

    dialog.hlb_selection.handle_selection("Walking")
    assert "Walking" in dialog.hlb_active.text()
    assert "HLB_Unlabeled" not in dialog.hlb_active.text()
    assert len(dialog.hlb_selection.selected_values) == 1

    dialog.hlb_selection.handle_selection("Grooming")
    assert "Walking" in dialog.hlb_active.text()
    assert "Grooming" in dialog.hlb_active.text()
    assert len(dialog.hlb_selection.selected_values) == 2

    remove_button = None
    for i in range(dialog.hlb_selection.tag_layout.count()):
        widget = dialog.hlb_selection.tag_layout.itemAt(i).widget()
        if widget.findChild(QLabel).text() == "Walking":
            remove_button = widget.findChild(QPushButton)
            break
    
    assert remove_button is not None, "Could not find remove button for 'Walking' tag"
    qtbot.mouseClick(remove_button, Qt.MouseButton.LeftButton)

    assert "Walking" not in dialog.hlb_active.text()
    assert "Grooming" in dialog.hlb_active.text()
    assert len(dialog.hlb_selection.selected_values) == 1

def test_retrieving_selected_values(qtbot, mock_categories_csv):
    dialog = AnnotationDialog()
    qtbot.addWidget(dialog)
    dialog.posture_selection.handle_selection("Sitting")
    dialog.hlb_selection.handle_selection("Walking")
    dialog.hlb_selection.handle_selection("Resting")
    posture_items = dialog.posture_list.selectedItems()
    hlb_items = dialog.hlb_list.selectedItems()
    assert len(posture_items) == 1
    assert posture_items[0].text() == "Sitting"
    selected_hlb = {item.text() for item in hlb_items}
    assert selected_hlb == {"Walking", "Resting"}

def test_keyboard_shortcuts_focus_combos(qtbot, mock_categories_csv):
    dialog = AnnotationDialog()
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.keyPress(dialog, Qt.Key.Key_1)
    assert dialog.posture_combo.view().isVisible()
    dialog.posture_combo.hidePopup()
    qtbot.keyPress(dialog, Qt.Key.Key_2)
    assert dialog.hlb_combo.view().isVisible()
    dialog.hlb_combo.hidePopup()