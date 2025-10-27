import sys
import json
import csv
from collections import defaultdict

from PyQt6.QtWidgets import (QApplication, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
                           QPushButton, QWidget, QDialogButtonBox, QComboBox,
                           QGridLayout, QFrame, QScrollArea, QLayout, QMessageBox, QCheckBox)
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QRect, QPoint, QTimer, QSettings
from PyQt6.QtGui import QKeyEvent
from src.utils import resource_path

# Constants
APP_NAME = "PAAWS-Annotation-Software"
ORGANIZATION_NAME = "PAAWS"
SETTINGS_DISABLE_ALERTS = "disableAlerts"

CAT_POSTURE = "POSTURE"
CAT_HLB = "HIGH LEVEL BEHAVIOR"
CAT_PA = "PA TYPE"
CAT_BP = "Behavioral Parameters"
CAT_ES = "Experimental situation"
CAT_NOTES = "Special Notes"

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
            TagWidget { 
                background-color: #3d3d3d; 
                border-radius: 4px; 
                padding: 2px; 
                margin: 2px;
                border: 1px solid transparent; /* Add transparent border for smooth transitions */
            }
            /* Style for invalid tags */
            TagWidget[invalid="true"] {
                border: 1px solid #e53935;
                background-color: #5f2a2a;
            }
            QPushButton { background-color: transparent; border: none; color: #888888; padding: 1px 6px; font-weight: bold; font-size: 13px; }
            QPushButton:hover { color: #ffffff; }
            QLabel { color: #ffffff; margin: 0; padding: 2px 6px; font-size: 12px; background-color: transparent; border: none; }
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 0, 2, 0)
        layout.setSpacing(2)
        
        self.label = QLabel(text)
        remove_btn = QPushButton("×")
        remove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        remove_btn.clicked.connect(lambda: self.removed.emit(self.label.text()))
        
        layout.addWidget(self.label)
        layout.addWidget(remove_btn)

    def set_invalid(self, is_invalid):
        self.setProperty("invalid", is_invalid)
        self.style().polish(self)
        self.style().unpolish(self)

class SelectionWidget(QWidget):
    selectionChanged = pyqtSignal()
    userMadeSelection = pyqtSignal()

    def __init__(self, combo, active_label, multi_select=False, parent=None):
        super().__init__(parent)
        self.combo = combo
        self.active_label = active_label
        self.selected_values = []
        self.multi_select = multi_select
        self.unlabeled_text = ""
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        if multi_select:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setStyleSheet("QScrollArea { border: none; background-color: transparent; }")
            self.tag_container = QWidget()
            self.tag_layout = FlowLayout(self.tag_container)
            self.tag_container.setLayout(self.tag_layout)
            scroll.setWidget(self.tag_container)
            scroll.setMinimumHeight(120); scroll.setMaximumHeight(180)
            layout.addWidget(scroll)
        
        layout.addWidget(combo)
        self.combo.currentTextChanged.connect(self._handle_combo_change)

    def set_unlabeled_text(self, text):
        self.unlabeled_text = text
        self.set_values([text])

    def set_values(self, values):
        self.selected_values.clear()
        if self.multi_select:
            while self.tag_layout.count() > 0:
                item = self.tag_layout.takeAt(0)
                if item and item.widget(): item.widget().deleteLater()
        
        values_to_set = values if (values and values[0] is not None) else [self.unlabeled_text]
        # Ensure unlabeled text is removed if other values are present
        if len(values_to_set) > 1 and self.unlabeled_text in values_to_set:
            values_to_set.remove(self.unlabeled_text)

        for value in values_to_set: self._add_value(value)

        if not self.selected_values:
            self._add_value(self.unlabeled_text)
        
        self._update_ui()
        self.selectionChanged.emit()

    def _handle_combo_change(self, text):
        if not text: return

        changed = False
        if not self.multi_select:
            if not self.selected_values or text != self.selected_values[0]:
                self.selected_values = [text]
                changed = True
        else: # Multi-select logic
            if text != self.unlabeled_text and text not in self.selected_values:
                if self.unlabeled_text in self.selected_values:
                    self._remove_value(self.unlabeled_text)
                self._add_value(text)
                changed = True
        
        if changed:
            self._update_ui()
            self.selectionChanged.emit()
            self.userMadeSelection.emit()

    def remove_tag(self, text):
        self._remove_value(text)
        if not self.selected_values:
            self._add_value(self.unlabeled_text)
        
        self._update_ui()
        self.selectionChanged.emit()

    def _add_value(self, text):
        if text and text not in self.selected_values:
            self.selected_values.append(text)
            if self.multi_select:
                tag = TagWidget(text)
                tag.removed.connect(self.remove_tag)
                self.tag_layout.addWidget(tag)

    def _remove_value(self, text):
        if text in self.selected_values:
            self.selected_values.remove(text)
        if self.multi_select:
            for i in range(self.tag_layout.count()):
                item = self.tag_layout.itemAt(i)
                widget = item.widget() if item else None
                if isinstance(widget, TagWidget) and widget.label.text() == text:
                    self.tag_layout.takeAt(i); widget.deleteLater()
                    break

    def _update_ui(self):
        self.update_active_label()
        if not self.multi_select and self.selected_values:
            current_selection = self.selected_values[0]
            if self.combo.currentText() != current_selection:
                self.combo.blockSignals(True)
                self.combo.setCurrentText(current_selection)
                self.combo.blockSignals(False)
        elif self.multi_select and self.combo.currentIndex() != 0:
             self.combo.blockSignals(True)
             self.combo.setCurrentIndex(0)
             self.combo.blockSignals(False)

    def update_active_label(self):
        if not self.selected_values:
            self.active_label.setText(self.unlabeled_text)
            return

        chunks, current_chunk = [], []
        valid_selections = [v for v in self.selected_values if v != self.unlabeled_text]
        if not valid_selections:
            self.active_label.setText(self.unlabeled_text)
            return

        for i, value in enumerate(valid_selections):
            current_chunk.append(value)
            if len(current_chunk) >= 2 or i == len(valid_selections) - 1:
                chunks.append(", ".join(current_chunk))
                current_chunk = []
        self.active_label.setText("\n".join(chunks))

    def set_invalid_style(self, is_invalid):
        self.setProperty("invalid", is_invalid)
        for widget in [self, self.combo, self.active_label]:
            widget.style().polish(widget); widget.style().unpolish(widget)

class AnnotationDialog(QDialog):
    def __init__(self, annotation=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Category Choices")
        self.setModal(True)
        self.setMinimumWidth(1200); self.setMinimumHeight(800)
        
        self.settings = QSettings(ORGANIZATION_NAME, APP_NAME)
        self.mappings = {}; self.full_categories = {}

        if not self.load_mappings() or not self.load_categories():
            QTimer.singleShot(0, self.reject); return

        self._init_ui()
        initial_data = self._get_initial_data(annotation)
        if initial_data:
            self._set_values_from_data(initial_data)

        initial_errors = self._get_validation_errors()
        if initial_errors:
            self.show_all_checkbox.setChecked(True)
            print("Loaded incompatible data, enabling 'Show all options' automatically.")

        self.show_all_checkbox.stateChanged.connect(self._on_settings_change)
        self.disable_alerts_checkbox.stateChanged.connect(self._on_settings_change)

        self.pa_selection.selectionChanged.connect(self._update_filters)
        self.hlb_selection.selectionChanged.connect(self._update_filters)
        self.posture_selection.selectionChanged.connect(self._update_filters)
        
        self.pa_selection.userMadeSelection.connect(self._handle_user_validation)
        self.hlb_selection.userMadeSelection.connect(self._handle_user_validation)
        self.posture_selection.userMadeSelection.connect(self._handle_user_validation)

        self._update_filters()
        self._run_validation_check(is_initial_load=True)

    def _init_ui(self):
        main_scroll = QScrollArea(); main_scroll.setWidgetResizable(True)
        main_widget = QWidget(); main_widget.setStyleSheet(self._get_stylesheet())
        main_layout = QVBoxLayout(main_widget); main_layout.setSpacing(24); main_layout.setContentsMargins(24, 24, 24, 24)
        
        options_layout = QHBoxLayout()
        self.show_all_checkbox = QCheckBox("Show all options (allows incompatible selections)")
        self.disable_alerts_checkbox = QCheckBox("Disable all pop-up warnings")
        self.disable_alerts_checkbox.setChecked(self.settings.value(SETTINGS_DISABLE_ALERTS, False, type=bool))
        options_layout.addWidget(self.show_all_checkbox); options_layout.addStretch(); options_layout.addWidget(self.disable_alerts_checkbox)
        main_layout.addLayout(options_layout)
        
        grid = QGridLayout(); grid.setSpacing(16); grid.setColumnMinimumWidth(0, 220); grid.setColumnStretch(1, 2)
        headers = ["Category", "Choice(s)", "Active labels"]
        for i, header in enumerate(headers):
            label = QLabel(header); label.setObjectName("headerLabel"); grid.addWidget(label, 0, i)
        
        self.posture_combo, self.hlb_combo, self.pa_combo, self.bp_combo, self.es_combo = (QComboBox() for _ in range(5))
        self.posture_active, self.hlb_active, self.pa_active, self.bp_active, self.es_active = (QLabel() for _ in range(5))
        
        self.posture_selection = SelectionWidget(self.posture_combo, self.posture_active, multi_select=False)
        self.hlb_selection = SelectionWidget(self.hlb_combo, self.hlb_active, multi_select=True)
        self.pa_selection = SelectionWidget(self.pa_combo, self.pa_active, multi_select=False)
        self.bp_selection = SelectionWidget(self.bp_combo, self.bp_active, multi_select=True)
        self.es_selection = SelectionWidget(self.es_combo, self.es_active, multi_select=False)
        self.all_selections = { CAT_POSTURE: self.posture_selection, CAT_HLB: self.hlb_selection, CAT_PA: self.pa_selection }

        self._populate_combos()

        categories_setup = [
            (f"{CAT_POSTURE} (Key 1)", self.posture_selection, self.posture_active),
            (f"{CAT_HLB} (Key 2)", self.hlb_selection, self.hlb_active),
            (f"{CAT_PA} (Key 3)", self.pa_selection, self.pa_active),
            (f"{CAT_BP} (Key 4)", self.bp_selection, self.bp_active),
            (f"{CAT_ES} (Key 5)", self.es_selection, self.es_active)
        ]
        for row, (title, sel, active) in enumerate(categories_setup, 1):
            label = QLabel(title); label.setProperty("category", "true")
            grid.addWidget(label, row, 0); grid.addWidget(sel, row, 1); grid.addWidget(active, row, 2)
        main_layout.addLayout(grid)
        
        notes_container = QWidget(); notes_container.setObjectName("notesContainer")
        notes_layout = QVBoxLayout(notes_container); notes_layout.setSpacing(12)
        notes_label = QLabel(f"{CAT_NOTES} (Key 6)"); notes_label.setProperty("category", "true")
        notes_layout.addWidget(notes_label)
        notes_sublabel = QLabel("Maximum 255 characters"); notes_sublabel.setObjectName("notesSublabel")
        notes_layout.addWidget(notes_sublabel)
        self.notes_edit = QLineEdit(); self.notes_edit.setMaxLength(255); self.notes_edit.setPlaceholderText("Enter any special notes here...")
        notes_layout.addWidget(self.notes_edit)
        main_layout.addWidget(notes_container)

        button_container = QWidget()
        button_layout = QHBoxLayout(button_container); button_layout.setSpacing(10)
        button_box = QDialogButtonBox()
        ok_button = QPushButton("Save"); cancel_button = QPushButton("Cancel")
        button_box.addButton(ok_button, QDialogButtonBox.ButtonRole.AcceptRole)
        button_box.addButton(cancel_button, QDialogButtonBox.ButtonRole.RejectRole)
        button_box.accepted.connect(self.accept); button_box.rejected.connect(self.reject)
        button_layout.addStretch(); button_layout.addWidget(button_box)
        main_layout.addWidget(button_container)
        
        main_scroll.setWidget(main_widget)
        dialog_layout = QVBoxLayout(self); dialog_layout.setContentsMargins(0, 0, 0, 0); dialog_layout.addWidget(main_scroll)
    
    def _get_initial_data(self, annotation):
        if annotation and hasattr(annotation, 'comments') and annotation.comments:
            try:
                return json.loads(annotation.comments[0]["body"])
            except Exception as e:
                QMessageBox.critical(self, "Load Error", f"Failed to parse annotation: {e}")
                return None
        elif hasattr(self.parent(), "annotation_manager") and hasattr(self.parent().annotation_manager, "last_used_labels"):
            d = self.parent().annotation_manager.last_used_labels
            if any(v for k, v in d.items() if k != "special_notes" or v):
                return [
                    {"category": CAT_POSTURE, "selectedValue": d["posture"]},
                    {"category": CAT_HLB, "selectedValue": d["hlb"]},
                    {"category": CAT_PA, "selectedValue": d["pa_type"]},
                    {"category": CAT_BP, "selectedValue": d["behavioral_params"]},
                    {"category": CAT_ES, "selectedValue": d["exp_situation"]},
                    {"category": CAT_NOTES, "selectedValue": d.get("special_notes", "")}
                ]
        return None

    def _set_values_from_data(self, data):
        for w in self.all_selections.values(): w.blockSignals(True)
        data_map = {item["category"]: item["selectedValue"] for item in data}
        self.posture_selection.set_values([data_map.get(CAT_POSTURE)])
        self.hlb_selection.set_values(data_map.get(CAT_HLB))
        self.pa_selection.set_values([data_map.get(CAT_PA)])
        self.bp_selection.set_values(data_map.get(CAT_BP))
        self.es_selection.set_values([data_map.get(CAT_ES)])
        self.notes_edit.setText(data_map.get(CAT_NOTES, ""))
        for w in self.all_selections.values(): w.blockSignals(False)

    def accept(self):
        errors = self._get_validation_errors()
        if not errors:
            super().accept()
            return
        
        error_messages = []
        if CAT_POSTURE in errors:
            error_messages.append(f"Posture '{errors[CAT_POSTURE][0]}' is incompatible.")
        if CAT_HLB in errors:
            error_messages.append(f"HLB(s) {', '.join(errors[CAT_HLB])} are incompatible.")
        
        msg = f"There are incompatible selections for PA Type '{self.pa_selection.selected_values[0]}':\n\n" + "\n".join(f"- {e}" for e in error_messages) + "\n\nDo you want to save anyway?"
        
        reply = QMessageBox.question(self, "Confirm Save", msg, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            super().accept()

    def get_all_selections(self):
        return { CAT_POSTURE: self.posture_selection.selected_values[0], CAT_HLB: self.hlb_selection.selected_values, CAT_PA: self.pa_selection.selected_values[0], CAT_BP: self.bp_selection.selected_values, CAT_ES: self.es_selection.selected_values[0], CAT_NOTES: self.notes_edit.text() }

    def _on_settings_change(self):
        self.settings.setValue(SETTINGS_DISABLE_ALERTS, self.disable_alerts_checkbox.isChecked())
        self._update_filters()
        self._run_validation_check()

    def _handle_user_validation(self):
        if self.show_all_checkbox.isChecked() and not self.disable_alerts_checkbox.isChecked():
            errors = self._get_validation_errors()
            if errors:
                error_messages = []
                if CAT_POSTURE in errors: error_messages.append(f"Posture '{errors[CAT_POSTURE][0]}' is incompatible.")
                if CAT_HLB in errors: error_messages.append(f"HLB(s) {', '.join(errors[CAT_HLB])} are incompatible.")
                msg = "A potential mismatch has been detected:\n\n" + "\n".join(f"- {e}" for e in error_messages)
                QMessageBox.warning(self, "Potential Mismatch", msg)
    
    def _update_filters(self):
        if self.show_all_checkbox.isChecked():
            self._update_combo_items(self.pa_combo, self.full_categories[CAT_PA])
            self._update_combo_items(self.hlb_combo, self.full_categories[CAT_HLB])
            self._update_combo_items(self.posture_combo, self.full_categories[CAT_POSTURE])
        else:
            self._apply_filters()
        self._run_validation_check()

    def _apply_filters(self):
        selected_pa = self.pa_selection.selected_values[0]
        selected_hlbs = []
        for h in self.hlb_selection.selected_values:
            if h != self.hlb_selection.unlabeled_text:
                selected_hlbs.append(h)
        selected_posture = self.posture_selection.selected_values[0]

        all_pas = self.full_categories[CAT_PA]
        if len(selected_hlbs) == 1:
            pas_for_hlb = set(self.mappings['HLB_to_PA'].get(selected_hlbs[0], all_pas))
        else:
            pas_for_hlb = set(all_pas)
        pas_for_posture = set(self.mappings['POS_to_PA'].get(selected_posture, all_pas))
        permissible_pas = sorted(list(pas_for_hlb.intersection(pas_for_posture)))
        permissible_pas.insert(0, all_pas[0])

        all_hlbs = self.full_categories[CAT_HLB]
        mapped_hlb = self.mappings['PA_to_HLB'].get(selected_pa)
        if mapped_hlb:
            permissible_hlb = [all_hlbs[0], mapped_hlb]
        else:
            permissible_hlb = all_hlbs

        all_postures = self.full_categories[CAT_POSTURE]
        mapped_postures = self.mappings['PA_to_POS'].get(selected_pa, all_postures)
        permissible_postures = [all_postures[0]] + sorted([p for p in mapped_postures if p != all_postures[0]])

        self._update_combo_items(self.pa_combo, permissible_pas, self.pa_selection)
        self._update_combo_items(self.hlb_combo, permissible_hlb, self.hlb_selection)
        self._update_combo_items(self.posture_combo, permissible_postures, self.posture_selection)

    def _run_validation_check(self, is_initial_load=False):
        self._clear_all_invalid_styles()
        errors = self._get_validation_errors()
        if not errors: return
        
        if is_initial_load:
            error_messages = []
            if CAT_POSTURE in errors: error_messages.append(f"Posture '{errors[CAT_POSTURE][0]}' is incompatible.")
            if CAT_HLB in errors: error_messages.append(f"HLB(s) {', '.join(errors[CAT_HLB])} are incompatible.")
            msg = "The loaded annotation has incompatible values:\n\n" + "\n".join(f"- {e}" for e in error_messages)
            QMessageBox.warning(self, "Incompatible Annotation", msg)
        
        if self.disable_alerts_checkbox.isChecked() or is_initial_load:
            self._apply_invalid_styles(errors)
            
    def _get_validation_errors(self):
        errors = defaultdict(list)
        selected_pa = self.pa_selection.selected_values[0]
        selected_posture = self.posture_selection.selected_values[0]
        
        if selected_pa == self.pa_selection.unlabeled_text: return {}

        allowed_postures = self.mappings.get('PA_to_POS', {}).get(selected_pa)
        if (allowed_postures is not None and selected_posture not in allowed_postures and 
            selected_posture != self.posture_selection.unlabeled_text):
            errors[CAT_POSTURE].append(selected_posture)

        allowed_hlb = self.mappings.get('PA_to_HLB', {}).get(selected_pa)
        if allowed_hlb is not None:
            for hlb in self.hlb_selection.selected_values:
                if hlb != allowed_hlb and hlb != self.hlb_selection.unlabeled_text:
                    errors[CAT_HLB].append(hlb)
            
        return dict(errors)

    def _apply_invalid_styles(self, errors):
        if errors:
            self.pa_selection.set_invalid_style(True)
        if CAT_POSTURE in errors:
            self.posture_selection.set_invalid_style(True)
        if CAT_HLB in errors:
            invalid_hlbs = set(errors[CAT_HLB])
            for i in range(self.hlb_selection.tag_layout.count()):
                item = self.hlb_selection.tag_layout.itemAt(i)
                widget = item.widget() if item else None
                if isinstance(widget, TagWidget) and widget.label.text() in invalid_hlbs:
                    widget.set_invalid(True)

    def _clear_all_invalid_styles(self):
        for sel in self.all_selections.values():
            sel.set_invalid_style(False)
        if self.hlb_selection.tag_layout:
            for i in range(self.hlb_selection.tag_layout.count()):
                item = self.hlb_selection.tag_layout.itemAt(i)
                widget = item.widget() if item else None
                if isinstance(widget, TagWidget):
                    widget.set_invalid(False)
        
    def keyPressEvent(self, event: QKeyEvent):
        if event.key() >= Qt.Key.Key_1 and event.key() <= Qt.Key.Key_5: self.selectCategoryByIndex(event.key() - Qt.Key.Key_1)
        super().keyPressEvent(event)
    def selectCategoryByIndex(self, index):
        category_combos = [ self.posture_combo, self.hlb_combo, self.pa_combo, self.bp_combo, self.es_combo ]
        if 0 <= index < len(category_combos): category_combos[index].showPopup()
    def load_mappings(self):
        try:
            path = resource_path('data/mapping/mapping.json')
            with open(path, 'r') as f: self.mappings = json.load(f)
            self.mappings['HLB_to_PA'] = defaultdict(list); [self.mappings['HLB_to_PA'][hlb].append(pa) for pa, hlb in self.mappings.get('PA_to_HLB', {}).items()]
            self.mappings['POS_to_PA'] = defaultdict(list); [[self.mappings['POS_to_PA'][pos].append(pa) for pos in postures] for pa, postures in self.mappings.get('PA_to_POS', {}).items()]
            return True
        except Exception as e: QMessageBox.critical(self, "Config Error", f"Could not load mapping.json:\n{e}"); return False
    def load_categories(self):
        try:
            path = resource_path('data/categories/categories.csv')
            with open(path, 'r') as f:
                categories = defaultdict(list); [categories[cat].append(val) for row in csv.DictReader(f) for cat, val in row.items() if val]
                self.full_categories = { CAT_POSTURE: ["Posture_Unlabeled"] + categories[CAT_POSTURE], CAT_HLB: ["HLB_Unlabeled"] + categories[CAT_HLB], CAT_PA: ["PA_Type_Unlabeled"] + categories[CAT_PA], CAT_BP: ["CP_Unlabeled"] + categories[CAT_BP], CAT_ES: ["ES_Unlabeled"] + categories[CAT_ES] }
            return True
        except Exception as e: QMessageBox.critical(self, "Config Error", f"Could not load categories.csv:\n{e}"); return False
    def _populate_combos(self):
        self.posture_combo.addItems(self.full_categories[CAT_POSTURE]); self.hlb_combo.addItems(self.full_categories[CAT_HLB]); self.pa_combo.addItems(self.full_categories[CAT_PA]); self.bp_combo.addItems(self.full_categories[CAT_BP]); self.es_combo.addItems(self.full_categories[CAT_ES])
        self.posture_selection.set_unlabeled_text(self.full_categories[CAT_POSTURE][0]); self.hlb_selection.set_unlabeled_text(self.full_categories[CAT_HLB][0]); self.pa_selection.set_unlabeled_text(self.full_categories[CAT_PA][0]); self.bp_selection.set_unlabeled_text(self.full_categories[CAT_BP][0]); self.es_selection.set_unlabeled_text(self.full_categories[CAT_ES][0])
    def _update_combo_items(self, combo, new_items, selection_widget=None):
        combo.blockSignals(True)
        current_val = selection_widget.selected_values[0] if selection_widget and not selection_widget.multi_select and selection_widget.selected_values else combo.currentText()
        combo.clear(); combo.addItems(new_items)
        if current_val in new_items: combo.setCurrentText(current_val)
        else:
            if selection_widget and not selection_widget.multi_select:
                selection_widget.set_values([new_items[0]])
                QMessageBox.information(self, "Selection Reset", f"'{current_val}' was reset due to incompatibility.")
        combo.blockSignals(False)
    def _get_stylesheet(self):
        return """
            QWidget { background-color: #1e1e1e; color: #ffffff; font-size: 13px; }
            QLabel#headerLabel { font-weight: bold; color: #ffffff; font-size: 14px; padding-bottom: 8px; }
            QLabel[category="true"] { padding: 8px 12px; background-color: #3d3d3d; border-radius: 4px; font-weight: bold; }
            QWidget#notesContainer { background-color: #2a2a2a; border-radius: 4px; padding: 12px; }
            QLabel#notesSublabel { color: #888888; font-size: 12px; padding: 4px 0; }
            QCheckBox { spacing: 8px; }
            QComboBox { background-color: #2d2d2d; border: 1px solid #3d3d3d; border-radius: 4px; padding: 8px 12px; min-width: 400px; }
            QWidget[invalid="true"] > QComboBox { border: 1px solid #e53935; }
            QLineEdit { padding: 10px; background-color: #2d2d2d; border: 1px solid #3d3d3d; border-radius: 4px; }
            QPushButton { padding: 10px 24px; border-radius: 4px; font-weight: bold; border: none; }
            QPushButton[text="Save"] { background-color: #2b79ff; color: white; }
            QPushButton[text="Save"]:hover { background-color: #3d8aff; }
            QPushButton[text="Cancel"] { background-color: #666666; color: white; }
            QPushButton[text="Cancel"]:hover { background-color: #777777; }
            QLabel { padding: 8px 12px; }
        """