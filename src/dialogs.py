from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
                           QPushButton, QWidget, QDialogButtonBox, QComboBox,
                           QGridLayout, QFrame, QScrollArea, QLayout)
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QRect, QPoint, QTimer
from PyQt6.QtGui import QKeyEvent
import json
import csv

class FlowLayout(QLayout):
    def __init__(self, parent=None, margin=0, spacing=-1):
        super().__init__(parent)
        self.itemList = []
        self.setContentsMargins(margin, margin, margin, margin)
        self.setSpacing(spacing)

    def __del__(self):
        item = self.takeAt(0)
        while item:
            item = self.takeAt(0)

    def addItem(self, item):
        self.itemList.append(item)

    def count(self):
        return len(self.itemList)

    def itemAt(self, index):
        if 0 <= index < len(self.itemList):
            return self.itemList[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self.itemList):
            return self.itemList.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        height = self.doLayout(QRect(0, 0, width, 0), True)
        return height

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self.doLayout(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self.itemList:
            size = size.expandedTo(item.minimumSize())
        margin = self.contentsMargins()
        size += QSize(2 * margin.left() + 2 * margin.right(), 2 * margin.top() + 2 * margin.bottom())
        return size

    def doLayout(self, rect, testOnly):
        x = rect.x()
        y = rect.y()
        lineHeight = 0
        spacing = self.spacing()

        for item in self.itemList:
            nextX = x + item.sizeHint().width() + spacing
            if nextX - spacing > rect.right() and lineHeight > 0:
                x = rect.x()
                y = y + lineHeight + spacing
                nextX = x + item.sizeHint().width() + spacing
                lineHeight = 0

            if not testOnly:
                item.setGeometry(QRect(QPoint(x, y), item.sizeHint()))

            x = nextX
            lineHeight = max(lineHeight, item.sizeHint().height())

        return y + lineHeight - rect.y()

class TagWidget(QFrame):
    removed = pyqtSignal(str)
    
    def __init__(self, text, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QFrame {
                background-color: #3d3d3d;
                border-radius: 4px;
                padding: 2px;
                margin: 2px;
            }
            QPushButton {
                background-color: transparent;
                border: none;
                color: #888888;
                padding: 1px 6px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                color: #ffffff;
            }
            QLabel {
                color: #ffffff;
                margin: 0;
                padding: 2px 6px;
                font-size: 12px;
            }
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 0, 2, 0)
        layout.setSpacing(2)
        
        label = QLabel(text)
        remove_btn = QPushButton("×")
        remove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        remove_btn.clicked.connect(lambda: self.removed.emit(text))
        
        layout.addWidget(label)
        layout.addWidget(remove_btn)

class SelectionWidget(QWidget):
    selectionChanged = pyqtSignal(list)
    
    def __init__(self, combo, active_label, multi_select=False, parent=None):
        super().__init__(parent)
        self.combo = combo
        self.active_label = active_label
        self.selected_values = []
        self.multi_select = multi_select
        self.last_selected = None
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        if multi_select:
            # Create scroll area for tags only for multi-select
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            scroll.setStyleSheet("""
                QScrollArea {
                    border: none;
                    background-color: transparent;
                }
                QScrollBar:vertical {
                    border: none;
                    background: #2d2d2d;
                    width: 10px;
                    margin: 0px;
                }
                QScrollBar::handle:vertical {
                    background: #666666;
                    min-height: 20px;
                    border-radius: 5px;
                }
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                    border: none;
                    background: none;
                }
            """)
            
            self.tag_container = QWidget()
            self.tag_layout = FlowLayout(self.tag_container)
            self.tag_container.setLayout(self.tag_layout)
            
            # Add initial default tag for multi-select
            if combo.count() > 0:
                default_text = combo.itemText(0)
                self.selected_values = [default_text]
                default_tag = TagWidget(default_text)
                default_tag.removed.connect(self.remove_tag)
                self.tag_layout.addWidget(default_tag)
            
            scroll.setWidget(self.tag_container)
            scroll.setMinimumHeight(120)
            scroll.setMaximumHeight(180)
            layout.addWidget(scroll)
        else:
            # For single select, just add the combo box and update the active label
            if combo.count() > 0:
                self.selected_values = [combo.itemText(0)]
                self.active_label.setText(combo.itemText(0))
        
        layout.addWidget(combo)
        self.combo.currentTextChanged.connect(self.handle_selection)
        
    def handle_selection(self, text):
        if text and text != self.combo.itemText(0):
            if not self.multi_select:
                self.selected_values = [text]
                self.update_active_label()
            else:
                if text not in self.selected_values:
                    if len(self.selected_values) == 1 and self.selected_values[0] == self.combo.itemText(0):
                        self.selected_values.clear()
                        item = self.tag_layout.takeAt(0)
                        if item and item.widget():
                            item.widget().deleteLater()
                    
                    self.selected_values.append(text)
                    tag = TagWidget(text)
                    tag.removed.connect(self.remove_tag)
                    self.tag_layout.addWidget(tag)
                    self.update_active_label()
            
            self.last_selected = text
            self.selectionChanged.emit(self.selected_values)
        
        # Set the combo box to show the last selected item
        if self.last_selected:
            index = self.combo.findText(self.last_selected)
            if index >= 0:
                self.combo.setCurrentIndex(index)
    
    def remove_tag(self, text):
        if text in self.selected_values and self.multi_select:
            self.selected_values.remove(text)
            for i in range(self.tag_layout.count()):
                item = self.tag_layout.itemAt(i)
                if item and isinstance(item.widget(), TagWidget) and item.widget().findChild(QLabel).text() == text:
                    item.widget().deleteLater()
                    break
            
            if not self.selected_values:
                default_text = self.combo.itemText(0)
                self.selected_values = [default_text]
                tag = TagWidget(default_text)
                tag.removed.connect(self.remove_tag)
                self.tag_layout.addWidget(tag)
            
            self.update_active_label()
            self.selectionChanged.emit(self.selected_values)
    
    def update_active_label(self):
        if not self.selected_values:
            self.active_label.setText(self.combo.itemText(0))
        else:
            # Format with line breaks every 2-3 items
            chunks = []
            current_chunk = []
            
            for i, value in enumerate(self.selected_values):
                current_chunk.append(value)
                if len(current_chunk) >= 2 or i == len(self.selected_values) - 1:
                    chunks.append(", ".join(current_chunk))
                    current_chunk = []
            
            self.active_label.setText("\n".join(chunks))

class AnnotationDialog(QDialog):
    def __init__(self, annotation=None, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.setWindowTitle("Category Choices")
        self.setModal(True)
        self.setMinimumWidth(1200)
        self.setMinimumHeight(800)
        
        main_scroll = QScrollArea()
        main_scroll.setWidgetResizable(True)
        main_scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: #1e1e1e;
            }
            QScrollBar:vertical {
                border: none;
                background: #2d2d2d;
                width: 12px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #666666;
                min-height: 24px;
                border-radius: 6px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                border: none;
                background: none;
            }
        """)
        
        main_widget = QWidget()
        main_widget.setStyleSheet("""
            QWidget {
                background-color: #1e1e1e;
            }
            QLabel {
                color: #ffffff;
                font-size: 13px;
            }
            QLabel[category="true"] {
                padding: 10px;
                background-color: #3d3d3d;
                border-radius: 4px;
                font-weight: bold;
                color: #ffffff;
            }
            QComboBox {
                background-color: #2d2d2d;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                color: #ffffff;
                padding: 8px 12px;
                min-width: 400px;
                font-size: 13px;
            }
            QComboBox::drop-down {
                border: none;
                width: 24px;
            }
            QComboBox::down-arrow {
                image: url(down-arrow.png);
                width: 14px;
                height: 14px;
            }
            QComboBox:hover {
                background-color: #353535;
                border-color: #4d4d4d;
            }
            QComboBox:focus {
                border-color: #5d5d5d;
            }
            QLineEdit {
                padding: 10px;
                background-color: #2d2d2d;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                color: #ffffff;
                font-size: 13px;
            }
            QLineEdit:focus {
                border-color: #5d5d5d;
            }
            QPushButton {
                padding: 10px 24px;
                border-radius: 4px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton[text="Save"] {
                background-color: #2b79ff;
                color: white;
                border: none;
            }
            QPushButton[text="Save"]:hover {
                background-color: #3d8aff;
            }
            QPushButton[text="Cancel"] {
                background-color: #666666;
                color: white;
                border: none;
            }
            QPushButton[text="Cancel"]:hover {
                background-color: #777777;
            }
        """)
        
        main_layout = QVBoxLayout(main_widget)
        main_layout.setSpacing(24)
        main_layout.setContentsMargins(24, 24, 24, 24)

        grid = QGridLayout()
        grid.setSpacing(16)
        grid.setColumnMinimumWidth(0, 220)
        grid.setColumnStretch(1, 2)

        # Headers with improved styling
        headers = ["Category", "Choice(s)", "Active labels"]
        for i, header in enumerate(headers):
            label = QLabel(header)
            label.setStyleSheet("""
                font-weight: bold;
                color: #ffffff;
                font-size: 14px;
                padding-bottom: 8px;
            """)
            grid.addWidget(label, 0, i)

        # Initialize comboboxes and labels
        self.posture_combo = QComboBox()
        self.hlb_combo = QComboBox()
        self.pa_combo = QComboBox()
        self.bp_combo = QComboBox()
        self.es_combo = QComboBox()

        # Initialize active labels with enhanced styling
        label_style = """
            color: #888888;
            font-size: 13px;
            padding: 8px 12px;
            background-color: #2d2d2d;
            border-radius: 4px;
            min-width: 300px;
        """
        self.posture_active = QLabel("Posture_Unlabeled")
        self.hlb_active = QLabel("HLB_Unlabeled")
        self.pa_active = QLabel("PA_Type_Unlabeled")
        self.bp_active = QLabel("CP_Unlabeled")
        self.es_active = QLabel("ES_Unlabeled")
        
        for label in [self.posture_active, self.hlb_active, self.pa_active, self.bp_active, self.es_active]:
            label.setStyleSheet(label_style)

        # Create selection widgets
        self.posture_selection = SelectionWidget(self.posture_combo, self.posture_active, multi_select=False)
        self.hlb_selection = SelectionWidget(self.hlb_combo, self.hlb_active, multi_select=True)
        self.pa_selection = SelectionWidget(self.pa_combo, self.pa_active, multi_select=False)
        self.bp_selection = SelectionWidget(self.bp_combo, self.bp_active, multi_select=True)
        self.es_selection = SelectionWidget(self.es_combo, self.es_active, multi_select=False)

        # Set minimum width for comboboxes
        for combo in [self.posture_combo, self.hlb_combo, self.pa_combo, self.bp_combo, self.es_combo]:
            combo.setMinimumWidth(400)
        
        # Load categories from CSV
        self.load_categories()
        
        # Add categories and selection widgets to grid with improved labels
        categories = [
            ("POSTURE (Key 1)", self.posture_selection, self.posture_active),
            ("HIGH LEVEL BEHAVIOR (Key 2)", self.hlb_selection, self.hlb_active),
            ("PA TYPE (Key 3)", self.pa_selection, self.pa_active),
            ("Behavioral Parameters (Key 4)", self.bp_selection, self.bp_active),
            ("Experimental Situation (Key 5)", self.es_selection, self.es_active)
        ]
        
        for row, (title, selection, active) in enumerate(categories, start=1):
            label = QLabel(title)
            label.setProperty("category", "true")
            label.setStyleSheet("""
                background-color: #3d3d3d;
                border-radius: 4px;
                padding: 8px 12px;
                font-weight: bold;
                color: #ffffff;
                font-size: 13px;
            """)
            grid.addWidget(label, row, 0)
            grid.addWidget(selection, row, 1)
            grid.addWidget(active, row, 2)

        main_layout.addLayout(grid)
        
        # Special Notes with improved styling
        notes_container = QWidget()
        notes_container.setStyleSheet("""
            QWidget {
                background-color: #2a2a2a;
                border-radius: 4px;
                padding: 12px;
            }
        """)
        notes_layout = QVBoxLayout(notes_container)
        notes_layout.setSpacing(12)
        
        notes_label = QLabel("Special Notes (Key 6)")
        notes_label.setProperty("category", "true")
        notes_layout.addWidget(notes_label)
        
        notes_sublabel = QLabel("Maximum 255 characters")
        notes_sublabel.setStyleSheet("color: #888888; font-size: 12px; padding: 4px 0;")
        notes_layout.addWidget(notes_sublabel)
        
        self.notes_edit = QLineEdit()
        self.notes_edit.setMaxLength(255)
        self.notes_edit.setPlaceholderText("Enter any special notes here...")
        notes_layout.addWidget(self.notes_edit)
        main_layout.addWidget(notes_container)
        # Add buttons
        button_container = QWidget()
        button_layout = QHBoxLayout(button_container)
        button_layout.setSpacing(10)
        
        button_box = QDialogButtonBox()
        ok_button = QPushButton("Save")
        cancel_button = QPushButton("Cancel")
        
        button_box.addButton(ok_button, QDialogButtonBox.ButtonRole.AcceptRole)
        button_box.addButton(cancel_button, QDialogButtonBox.ButtonRole.RejectRole)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        
        button_layout.addStretch()
        button_layout.addWidget(button_box)
        main_layout.addWidget(button_container)
        
        # Set main scroll area and dialog layout
        main_scroll.setWidget(main_widget)
        dialog_layout = QVBoxLayout(self)
        dialog_layout.setContentsMargins(0, 0, 0, 0)
        dialog_layout.addWidget(main_scroll)
        
        # Set values from annotation or default labels
        if annotation:
            try:
                comment_data = json.loads(annotation.comments[0]["body"])
                self._set_values_from_data(comment_data)
            except Exception as e:
                print(f"Error parsing annotation data: {str(e)}")
        elif hasattr(parent, "annotation_manager") and any(v for v in parent.annotation_manager.default_labels.values()):
            # Use default labels from annotation manager if available
            default_labels = parent.annotation_manager.default_labels
            comment_data = [
                {"category": "POSTURE", "selectedValue": default_labels["posture"]},
                {"category": "HIGH LEVEL BEHAVIOR", "selectedValue": default_labels["hlb"]},
                {"category": "PA TYPE", "selectedValue": default_labels["pa_type"]},
                {"category": "Behavioral Parameters", "selectedValue": default_labels["behavioral_params"]},
                {"category": "Experimental situation", "selectedValue": default_labels["exp_situation"]},
                {"category": "Special Notes", "selectedValue": default_labels["special_notes"]}
            ]
            self._set_values_from_data(comment_data)

    def _set_values_from_data(self, comment_data):
        """Helper method to set values from comment data"""
        for item in comment_data:
            if item["category"] == "POSTURE" and item["selectedValue"]:
                self.posture_selection.handle_selection(item["selectedValue"])
            elif item["category"] == "HIGH LEVEL BEHAVIOR":
                values = item["selectedValue"] if isinstance(item["selectedValue"], list) else []
                for value in values:
                    if value:
                        self.hlb_selection.handle_selection(value)
            elif item["category"] == "PA TYPE" and item["selectedValue"]:
                self.pa_selection.handle_selection(item["selectedValue"])
            elif item["category"] == "Behavioral Parameters":
                values = item["selectedValue"] if isinstance(item["selectedValue"], list) else []
                for value in values:
                    if value:
                        self.bp_selection.handle_selection(value)
            elif item["category"] == "Experimental situation" and item["selectedValue"]:
                self.es_selection.handle_selection(item["selectedValue"])
            elif item["category"] == "Special Notes" and item["selectedValue"]:
                self.notes_edit.setText(item["selectedValue"])

    def getSelectedValues(self, selection_widget):
        """Helper method to get selected values from a selection widget"""
        return selection_widget.selected_values

    @property
    def posture_list(self):
        return self._create_mock_list(self.posture_selection)
    
    @property
    def hlb_list(self):
        return self._create_mock_list(self.hlb_selection)
    
    @property
    def pa_list(self):
        return self._create_mock_list(self.pa_selection)
    
    @property
    def bp_list(self):
        return self._create_mock_list(self.bp_selection)
    
    @property
    def es_list(self):
        return self._create_mock_list(self.es_selection)

    def _create_mock_list(self, selection_widget):
        class MockListItem:
            def __init__(self, text):
                self._text = text
            def text(self):
                return self._text
        
        class MockList:
            def __init__(self, values):
                self._values = values
            def selectedItems(self):
                return [MockListItem(v) for v in self._values]
        
        values = selection_widget.selected_values
        return MockList(values if values else [selection_widget.combo.itemText(0)])
            
    def keyPressEvent(self, event: QKeyEvent):
        if event.key() >= Qt.Key.Key_1 and event.key() <= Qt.Key.Key_5:
            index = event.key() - Qt.Key.Key_1  # Convert key to 0-based index
            self.selectCategoryByIndex(index)
        super().keyPressEvent(event)

    def selectCategoryByIndex(self, index):
        """Select the appropriate category combo based on numeric key index (0-4)"""
        category_combos = [
            self.posture_combo,
            self.hlb_combo,
            self.pa_combo,
            self.bp_combo,
            self.es_combo
        ]
        
        if 0 <= index < len(category_combos):
            target_combo = category_combos[index]
            target_combo.showPopup()
            QTimer.singleShot(0, lambda: self.setFocus())
                
    def load_categories(self):
        """Load categories from the CSV file"""
        try:
            with open('data/categories/categories.csv', 'r') as f:
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
                
                self.posture_combo.addItems(categories['POSTURE'])
                self.hlb_combo.addItems(categories['HIGH LEVEL BEHAVIOR'])
                self.pa_combo.addItems(categories['PA TYPE'])
                self.bp_combo.addItems(categories['Behavioral Parameters'])
                self.es_combo.addItems(categories['Experimental situation'])
                
        except Exception as e:
            print(f"Error loading categories: {str(e)}")
            # Add default items if CSV loading fails
            self.posture_combo.addItem("Posture_Unlabeled")
            self.hlb_combo.addItem("HLB_Unlabeled")
            self.pa_combo.addItem("PA_Type_Unlabeled")
            self.bp_combo.addItem("CP_Unlabeled")
            self.es_combo.addItem("ES_Unlabeled")
