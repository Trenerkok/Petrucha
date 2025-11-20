import sys
import os
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QTextEdit, QLineEdit, QPushButton, 
                             QLabel, QComboBox, QCheckBox, QGroupBox, QTabWidget,
                             QProgressBar, QTableWidget, QTableWidgetItem, QHeaderView,
                             QFileDialog, QDialog, QFormLayout, QListWidget, QListWidgetItem,
                             QMessageBox, QScrollArea, QSizePolicy, QFrame)
from PyQt6.QtCore import Qt, pyqtSlot, QSize
from PyQt6.QtGui import QFont, QTextCursor, QColor, QIcon, QPainter, QPainterPath, QFontMetrics

from core_worker import AssistantWorker
from config_manager import ConfigManager

# --- Styles ---
STYLE_SHEET = """
    /* Main Window & General */
    QMainWindow { background-color: #343541; color: #ECECF1; }
    QWidget { font-family: 'Segoe UI', sans-serif; font-size: 14px; color: #ECECF1; }
    
    /* Sidebar */
    QListWidget#Sidebar { 
        background-color: #202123; 
        border: none; 
        border-right: 1px solid #4d4d4f; 
        font-size: 15px;
        outline: none;
    }
    QListWidget#Sidebar::item { 
        padding: 15px; 
        color: #ECECF1;
        border-bottom: 1px solid #2b2c2f;
    }
    QListWidget#Sidebar::item:selected { 
        background-color: #343541; 
        color: #ffffff; 
        border-left: 3px solid #10a37f; /* ChatGPT Green Accent */
    }
    QListWidget#Sidebar::item:hover {
        background-color: #2A2B32;
    }

    /* Chat Area */
    QScrollArea#ChatScroll {
        background-color: #343541;
        border: none;
    }
    QWidget#ChatContent {
        background-color: #343541;
    }
    
    /* Inputs */
    QLineEdit, QTextEdit, QPlainTextEdit { 
        background-color: #40414F; 
        color: #ECECF1; 
        border: 1px solid #565869; 
        border-radius: 6px; 
        padding: 10px;
    }
    QLineEdit:focus {
        border: 1px solid #10a37f;
    }

    /* Buttons */
    QPushButton { 
        padding: 8px 15px; 
        background-color: #444654; 
        color: #ECECF1; 
        border: 1px solid #565869; 
        border-radius: 5px; 
        font-weight: bold;
    }
    QPushButton:hover { 
        background-color: #505260; 
    }
    QPushButton:checked { 
        background-color: #10a37f; 
        border-color: #10a37f;
        color: white;
    }
    
    /* Specific Button Overrides */
    QPushButton#StopBtn { 
        background-color: #ef4444; 
        border-color: #ef4444;
        color: white;
    }
    QPushButton#StopBtn:hover { 
        background-color: #dc2626; 
    }
    
    /* Tables & Lists */
    QTableWidget, QListWidget { 
        background-color: #202123; 
        color: #ECECF1; 
        border: 1px solid #565869; 
        gridline-color: #444654;
    }
    QHeaderView::section { 
        background-color: #343541; 
        color: #ECECF1; 
        padding: 8px; 
        border: none; 
        font-weight: bold; 
    }
    QTableWidget::item {
        padding: 5px;
    }
    QTableWidget::item:selected {
        background-color: #40414F;
    }

    /* GroupBox & Labels */
    QGroupBox {
        border: 1px solid #565869;
        border-radius: 5px;
        margin-top: 20px;
        font-weight: bold;
        color: #ECECF1;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        left: 10px;
        padding: 0 3px;
    }
    QLabel {
        color: #ECECF1;
    }

    /* ComboBox */
    QComboBox {
        background-color: #40414F;
        color: #ECECF1;
        border: 1px solid #565869;
        border-radius: 5px;
        padding: 5px;
    }
    QComboBox::drop-down {
        border: none;
    }
    QComboBox QAbstractItemView {
        background-color: #202123;
        color: #ECECF1;
        selection-background-color: #40414F;
    }

    /* Scrollbars */
    QScrollBar:vertical {
        border: none;
        background: #202123;
        width: 10px;
        margin: 0px;
    }
    QScrollBar::handle:vertical {
        background: #565869;
        min-height: 20px;
        border-radius: 5px;
    }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
        height: 0px;
    }
"""

# --- Custom Widgets ---

class MessageBubble(QFrame):
    """
    A custom widget to render chat messages as bubbles.
    Includes logic to calculate width dynamically so text doesn't collapse.
    """
    def __init__(self, text, role="user", parent=None):
        super().__init__(parent)
        self.role = role
        self.text = text
        self.init_ui()

    def init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 5, 0, 5)
        
        # Bubble Label
        self.lbl = QLabel(self.text)
        self.lbl.setWordWrap(True)
        self.lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        font = QFont("Segoe UI", 11)
        self.lbl.setFont(font)
        
        # --- FIX: Dynamic Width Calculation ---
        # Calculate how wide the text wants to be on a single line
        metrics = QFontMetrics(font)
        text_width = metrics.horizontalAdvance(self.text)
        
        # Add padding for margins
        bubble_padding = 40 
        
        # Determine target width:
        # - At least 50px
        # - At most 650px (to look like a chat bubble)
        # - Otherwise, exactly as wide as the text needs
        target_width = max(50, min(text_width + bubble_padding, 650))
        
        self.lbl.setMinimumWidth(target_width)
        self.lbl.setMaximumWidth(650)
        
        # Ensure the label tries to expand to its minimum width
        self.lbl.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Preferred)

        # Styling based on role
        if self.role == "user":
            layout.addStretch()
            self.lbl.setStyleSheet("""
                background-color: #444654; 
                color: white; 
                border-radius: 10px; 
                padding: 10px;
            """)
            layout.addWidget(self.lbl)
        else: # assistant
            self.lbl.setStyleSheet("""
                background-color: #202123; 
                color: white; 
                border: 1px solid #565869;
                border-radius: 10px; 
                padding: 10px;
            """)
            layout.addWidget(self.lbl)
            layout.addStretch()

# --- Dialogs ---

class EntryEditDialog(QDialog):
    def __init__(self, data=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Редагування запису")
        self.resize(500, 300)
        self.data = data or {}
        
        layout = QFormLayout(self)
        
        self.inp_id = QLineEdit(self.data.get("id", ""))
        if data: self.inp_id.setReadOnly(True)
        layout.addRow("Внутрішній ID:", self.inp_id)
        
        self.inp_name = QLineEdit(self.data.get("display_name", ""))
        layout.addRow("Назва (для списку):", self.inp_name)
        
        self.inp_voice = QLineEdit(", ".join(self.data.get("voice_names", [])))
        self.inp_voice.setPlaceholderText("steam, стім, ігри")
        layout.addRow("Голосові фрази:", self.inp_voice)
        
        self.combo_type = QComboBox()
        self.combo_type.addItems(["app", "file", "folder", "website"])
        self.combo_type.setCurrentText(self.data.get("type", "app"))
        layout.addRow("Тип:", self.combo_type)
        
        path_box = QHBoxLayout()
        self.inp_path = QLineEdit(self.data.get("path_or_url", ""))
        path_box.addWidget(self.inp_path)
        btn_browse = QPushButton("...")
        btn_browse.clicked.connect(self.browse)
        path_box.addWidget(btn_browse)
        layout.addRow("Шлях / URL:", path_box)
        
        self.inp_comment = QLineEdit(self.data.get("comment", ""))
        layout.addRow("Коментар:", self.inp_comment)
        
        btn_box = QHBoxLayout()
        btn_save = QPushButton("Зберегти")
        btn_save.clicked.connect(self.accept)
        btn_cancel = QPushButton("Скасувати")
        btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(btn_save)
        btn_box.addWidget(btn_cancel)
        layout.addRow(btn_box)

    def browse(self):
        t = self.combo_type.currentText()
        if t == "folder":
            d = QFileDialog.getExistingDirectory(self, "Оберіть папку")
            if d: self.inp_path.setText(d)
        elif t in ["app", "file"]:
            f, _ = QFileDialog.getOpenFileName(self, "Оберіть файл")
            if f: self.inp_path.setText(f)

    def get_data(self):
        return {
            "id": self.inp_id.text().strip(),
            "display_name": self.inp_name.text().strip(),
            "voice_names": [x.strip() for x in self.inp_voice.text().split(",") if x.strip()],
            "type": self.combo_type.currentText(),
            "path_or_url": self.inp_path.text().strip(),
            "comment": self.inp_comment.text().strip()
        }

class WorkspaceEditDialog(QDialog):
    def __init__(self, ws_data=None, all_entries=[], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Редагування режиму")
        self.resize(600, 500)
        self.data = ws_data or {}
        self.all_entries = all_entries
        
        layout = QVBoxLayout(self)
        
        form = QFormLayout()
        self.inp_id = QLineEdit(self.data.get("id", ""))
        if ws_data: self.inp_id.setReadOnly(True)
        form.addRow("ID:", self.inp_id)
        
        self.inp_name = QLineEdit(self.data.get("display_name", ""))
        form.addRow("Назва:", self.inp_name)
        
        self.inp_voice = QLineEdit(", ".join(self.data.get("voice_names", [])))
        form.addRow("Голосові фрази:", self.inp_voice)
        
        self.inp_desc = QLineEdit(self.data.get("description", ""))
        form.addRow("Опис:", self.inp_desc)
        layout.addLayout(form)
        
        layout.addWidget(QLabel("Кроки виконання:"))
        self.steps_list = QListWidget()
        for step in self.data.get("steps", []):
            self.add_step_item(step)
        layout.addWidget(self.steps_list)
        
        btn_step_box = QHBoxLayout()
        btn_add = QPushButton("+ Додати дію")
        btn_add.clicked.connect(self.add_step_dialog)
        btn_del = QPushButton("- Видалити дію")
        btn_del.clicked.connect(self.remove_step)
        btn_step_box.addWidget(btn_add)
        btn_step_box.addWidget(btn_del)
        layout.addLayout(btn_step_box)
        
        btn_box = QHBoxLayout()
        btn_save = QPushButton("Зберегти")
        btn_save.clicked.connect(self.accept)
        btn_cancel = QPushButton("Скасувати")
        btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(btn_save)
        btn_box.addWidget(btn_cancel)
        layout.addLayout(btn_box)

    def add_step_item(self, step):
        act = step.get("action")
        detail = step.get("entry_id") or step.get("app_id") or step.get("url") or step.get("subaction") or ""
        self.steps_list.addItem(f"{act}: {detail}")
        self.steps_list.item(self.steps_list.count()-1).setData(Qt.ItemDataRole.UserRole, step)

    def add_step_dialog(self):
        d = QDialog(self)
        d.setWindowTitle("Додати крок")
        l = QFormLayout(d)
        
        c_act = QComboBox()
        c_act.addItems(["OPEN_ENTRY", "CLOSE_APP", "OPEN_WEBSITE", "WINDOW", "WAIT"])
        l.addRow("Дія:", c_act)
        
        c_entry = QComboBox()
        c_entry.addItems([e['id'] for e in self.all_entries])
        l.addRow("Запис (для Open/Close):", c_entry)
        
        i_param = QLineEdit()
        i_param.setPlaceholderText("URL / subaction / seconds")
        l.addRow("Параметр:", i_param)
        
        b = QPushButton("Додати")
        b.clicked.connect(d.accept)
        l.addRow(b)
        
        if d.exec():
            act = c_act.currentText()
            step = {"action": act}
            if act == "OPEN_ENTRY": step["entry_id"] = c_entry.currentText()
            elif act == "CLOSE_APP": step["app_id"] = c_entry.currentText()
            elif act == "OPEN_WEBSITE": step["url"] = i_param.text()
            elif act == "WINDOW": step["subaction"] = i_param.text()
            elif act == "WAIT": step["seconds"] = i_param.text()
            self.add_step_item(step)

    def remove_step(self):
        row = self.steps_list.currentRow()
        if row >= 0: self.steps_list.takeItem(row)

    def get_data(self):
        steps = []
        for i in range(self.steps_list.count()):
            steps.append(self.steps_list.item(i).data(Qt.ItemDataRole.UserRole))
        return {
            "id": self.inp_id.text().strip(),
            "display_name": self.inp_name.text().strip(),
            "voice_names": [x.strip() for x in self.inp_voice.text().split(",") if x.strip()],
            "description": self.inp_desc.text().strip(),
            "steps": steps
        }

class IoTEditDialog(QDialog):
    def __init__(self, data=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Редагування IoT пристрою")
        self.resize(500, 600)
        self.data = data or {}
        
        layout = QVBoxLayout(self)
        form = QFormLayout()
        
        self.inp_id = QLineEdit(self.data.get("id", ""))
        if data: self.inp_id.setReadOnly(True)
        form.addRow("ID:", self.inp_id)
        
        self.inp_name = QLineEdit(self.data.get("display_name", ""))
        form.addRow("Назва:", self.inp_name)
        
        self.combo_conn = QComboBox()
        self.combo_conn.addItems(["HTTP", "MQTT", "Serial"])
        self.combo_conn.setCurrentText(self.data.get("connection_type", "HTTP"))
        form.addRow("Тип підключення:", self.combo_conn)
        
        self.inp_params = QTextEdit()
        self.inp_params.setPlaceholderText('{"url": "...", "method": "GET"}')
        import json
        self.inp_params.setText(json.dumps(self.data.get("connection_params", {}), indent=2))
        self.inp_params.setMaximumHeight(100)
        form.addRow("Параметри (JSON):", self.inp_params)
        
        layout.addLayout(form)
        
        layout.addWidget(QLabel("Дії (Actions):"))
        self.actions_list = QListWidget()
        for act in self.data.get("actions", []):
            self.add_action_item(act)
        layout.addWidget(self.actions_list)
        
        btn_act_box = QHBoxLayout()
        btn_add_act = QPushButton("+ Дія")
        btn_add_act.clicked.connect(self.add_action_dialog)
        btn_del_act = QPushButton("- Дія")
        btn_del_act.clicked.connect(self.remove_action)
        btn_act_box.addWidget(btn_add_act)
        btn_act_box.addWidget(btn_del_act)
        layout.addLayout(btn_act_box)
        
        btn_box = QHBoxLayout()
        btn_save = QPushButton("Зберегти")
        btn_save.clicked.connect(self.accept)
        btn_cancel = QPushButton("Скасувати")
        btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(btn_save)
        btn_box.addWidget(btn_cancel)
        layout.addLayout(btn_box)

    def add_action_item(self, act):
        self.actions_list.addItem(f"{act['name']} ({act['display_name']})")
        self.actions_list.item(self.actions_list.count()-1).setData(Qt.ItemDataRole.UserRole, act)

    def add_action_dialog(self):
        d = QDialog(self)
        l = QFormLayout(d)
        i_name = QLineEdit()
        l.addRow("Name (internal):", i_name)
        i_disp = QLineEdit()
        l.addRow("Display Name:", i_disp)
        i_voice = QLineEdit()
        l.addRow("Voice Phrases:", i_voice)
        i_pay = QLineEdit()
        l.addRow("Payload/Command:", i_pay)
        b = QPushButton("Add")
        b.clicked.connect(d.accept)
        l.addRow(b)
        
        if d.exec():
            self.add_action_item({
                "name": i_name.text(),
                "display_name": i_disp.text(),
                "voice_phrases": [x.strip() for x in i_voice.text().split(",")],
                "payload": i_pay.text()
            })

    def remove_action(self):
        row = self.actions_list.currentRow()
        if row >= 0: self.actions_list.takeItem(row)

    def get_data(self):
        import json
        try:
            params = json.loads(self.inp_params.toPlainText())
        except: params = {}
        
        actions = []
        for i in range(self.actions_list.count()):
            actions.append(self.actions_list.item(i).data(Qt.ItemDataRole.UserRole))
            
        return {
            "id": self.inp_id.text().strip(),
            "display_name": self.inp_name.text().strip(),
            "connection_type": self.combo_conn.currentText(),
            "connection_params": params,
            "actions": actions
        }

# --- Main Window ---

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Petrucha Voice Assistant")
        self.resize(1200, 800)
        self.cfg = ConfigManager()
        self.worker = AssistantWorker()
        
        # Signals
        self.worker.sig_user_text.connect(self.add_user_msg)
        self.worker.sig_assistant_text.connect(self.add_bot_msg)
        self.worker.sig_status.connect(self.update_status)
        self.worker.sig_mic_level.connect(self.update_mic)
        
        self.init_ui()

    def init_ui(self):
        self.setStyleSheet(STYLE_SHEET)
        
        # Main Layout: Sidebar + Content
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Sidebar
        self.sidebar = QListWidget()
        self.sidebar.setObjectName("Sidebar")
        self.sidebar.setFixedWidth(250)
        self.sidebar.addItems(["Головне", "Програми та файли", "Режими", "IoT-пристрої", "Нотатки", "Налаштування"])
        self.sidebar.currentRowChanged.connect(self.switch_tab)
        main_layout.addWidget(self.sidebar)

        # Content Area (Stacked)
        self.content_area = QWidget()
        self.content_layout = QVBoxLayout(self.content_area)
        self.content_layout.setContentsMargins(20, 20, 20, 20)
        
        # Create Pages
        self.page_chat = self.create_chat_page()
        self.page_entries = self.create_entries_page()
        self.page_workspaces = self.create_workspaces_page()
        self.page_iot = self.create_iot_page()
        self.page_notes = self.create_notes_page()
        self.page_settings = self.create_settings_page()
        
        # Add to layout (hidden by default, managed by switch_tab)
        self.pages = [self.page_chat, self.page_entries, self.page_workspaces, self.page_iot, self.page_notes, self.page_settings]
        for p in self.pages:
            self.content_layout.addWidget(p)
            p.hide()
        
        main_layout.addWidget(self.content_area)
        
        # Show first page
        self.sidebar.setCurrentRow(0)

    # --- Pages Creation ---

    def create_chat_page(self):
        w = QWidget()
        l = QVBoxLayout(w)
        
        # Header
        head = QHBoxLayout()
        title = QLabel("Petrucha Assistant")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: #ECECF1;")
        head.addWidget(title)
        head.addStretch()
        self.lbl_status = QLabel("Очікую")
        self.lbl_status.setStyleSheet("color: #8e8ea0; font-weight: bold;")
        head.addWidget(self.lbl_status)
        l.addLayout(head)
        
        # Chat Area (Scrollable)
        self.chat_scroll = QScrollArea()
        self.chat_scroll.setObjectName("ChatScroll")
        self.chat_scroll.setWidgetResizable(True)
        
        self.chat_content = QWidget()
        self.chat_content.setObjectName("ChatContent")
        self.chat_layout = QVBoxLayout(self.chat_content)
        self.chat_layout.addStretch() # Push messages to bottom
        
        self.chat_scroll.setWidget(self.chat_content)
        l.addWidget(self.chat_scroll)
        
        # Mic Bar
        self.mic_bar = QProgressBar()
        self.mic_bar.setFixedHeight(4)
        self.mic_bar.setTextVisible(False)
        self.mic_bar.setRange(0, 100)
        l.addWidget(self.mic_bar)
        
        # Input Area
        inp_box = QHBoxLayout()
        self.btn_mic = QPushButton("Слухати")
        self.btn_mic.setCheckable(True)
        self.btn_mic.clicked.connect(self.toggle_mic)
        inp_box.addWidget(self.btn_mic)
        
        self.inp_text = QLineEdit()
        self.inp_text.setPlaceholderText("Напишіть повідомлення...")
        self.inp_text.returnPressed.connect(self.send_msg)
        inp_box.addWidget(self.inp_text)
        
        btn_send = QPushButton("Надіслати")
        btn_send.clicked.connect(self.send_msg)
        inp_box.addWidget(btn_send)
        
        l.addLayout(inp_box)
        return w

    def create_entries_page(self):
        w = QWidget()
        l = QVBoxLayout(w)
        
        l.addWidget(QLabel("<h2>Програми та файли</h2>"))
        l.addWidget(QLabel("Додайте сюди програми, папки або сайти, щоб відкривати їх голосом."))
        
        self.table_entries = QTableWidget()
        self.table_entries.setColumnCount(5)
        self.table_entries.setHorizontalHeaderLabels(["ID", "Назва", "Голосові фрази", "Тип", "Шлях/URL"])
        self.table_entries.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        l.addWidget(self.table_entries)
        
        btn_box = QHBoxLayout()
        b_add = QPushButton("+ Додати запис")
        b_add.clicked.connect(self.add_entry)
        b_edit = QPushButton("Редагувати")
        b_edit.clicked.connect(self.edit_entry)
        b_del = QPushButton("Видалити")
        b_del.clicked.connect(self.del_entry)
        btn_box.addWidget(b_add)
        btn_box.addWidget(b_edit)
        btn_box.addWidget(b_del)
        l.addLayout(btn_box)
        
        self.refresh_entries()
        return w

    def create_workspaces_page(self):
        w = QWidget()
        l = QVBoxLayout(w)
        l.addWidget(QLabel("<h2>Режими (Сценарії)</h2>"))
        l.addWidget(QLabel("Створюйте послідовності дій для однієї команди."))
        
        self.list_ws = QListWidget()
        l.addWidget(self.list_ws)
        
        btn_box = QHBoxLayout()
        b_add = QPushButton("+ Додати режим")
        b_add.clicked.connect(self.add_ws)
        b_edit = QPushButton("Редагувати")
        b_edit.clicked.connect(self.edit_ws)
        b_del = QPushButton("Видалити")
        b_del.clicked.connect(self.del_ws)
        btn_box.addWidget(b_add)
        btn_box.addWidget(b_edit)
        btn_box.addWidget(b_del)
        l.addLayout(btn_box)
        
        self.refresh_ws()
        return w

    def create_iot_page(self):
        w = QWidget()
        l = QVBoxLayout(w)
        l.addWidget(QLabel("<h2>IoT Пристрої</h2>"))
        l.addWidget(QLabel("Налаштування розумних пристроїв (HTTP, MQTT, Serial)."))
        
        self.list_iot = QListWidget()
        l.addWidget(self.list_iot)
        
        btn_box = QHBoxLayout()
        b_add = QPushButton("+ Додати пристрій")
        b_add.clicked.connect(self.add_iot)
        b_edit = QPushButton("Редагувати")
        b_edit.clicked.connect(self.edit_iot)
        b_del = QPushButton("Видалити")
        b_del.clicked.connect(self.del_iot)
        btn_box.addWidget(b_add)
        btn_box.addWidget(b_edit)
        btn_box.addWidget(b_del)
        l.addLayout(btn_box)
        
        self.refresh_iot()
        return w

    def create_notes_page(self):
        w = QWidget()
        l = QVBoxLayout(w)
        l.addWidget(QLabel("<h2>Нотатки</h2>"))
        self.notes_view = QTextEdit()
        self.notes_view.setReadOnly(True)
        l.addWidget(self.notes_view)
        
        b_refresh = QPushButton("Оновити список")
        b_refresh.clicked.connect(self.load_notes)
        l.addWidget(b_refresh)
        return w

    def create_settings_page(self):
        w = QWidget()
        l = QVBoxLayout(w)
        l.addWidget(QLabel("<h2>Налаштування</h2>"))
        
        # STT
        g_stt = QGroupBox("Розпізнавання мови (STT)")
        gl_stt = QVBoxLayout()
        self.c_stt = QComboBox()
        self.c_stt.addItems(["vosk", "online"])
        self.c_stt.setCurrentText(self.cfg.get("stt_backend", "vosk"))
        gl_stt.addWidget(self.c_stt)
        g_stt.setLayout(gl_stt)
        l.addWidget(g_stt)
        
        # LLM
        g_llm = QGroupBox("Мовна модель (LLM)")
        gl_llm = QVBoxLayout()
        self.c_llm = QComboBox()
        self.c_llm.addItems(["local", "gemini"])
        self.c_llm.setCurrentText(self.cfg.get("llm_backend_default", "local"))
        gl_llm.addWidget(QLabel("Провайдер:"))
        gl_llm.addWidget(self.c_llm)
        
        self.i_gemini = QLineEdit(self.cfg.get("gemini_api_key", ""))
        self.i_gemini.setPlaceholderText("Gemini API Key")
        self.i_gemini.setEchoMode(QLineEdit.EchoMode.Password)
        gl_llm.addWidget(QLabel("Gemini Key:"))
        gl_llm.addWidget(self.i_gemini)
        
        g_llm.setLayout(gl_llm)
        l.addWidget(g_llm)
        
        # TTS
        g_tts = QGroupBox("Озвучення (TTS)")
        gl_tts = QVBoxLayout()
        self.c_tts = QComboBox()
        self.c_tts.addItems(["gtts", "pyttsx3"])
        self.c_tts.setCurrentText(self.cfg.get("tts_engine", "gtts"))
        gl_tts.addWidget(self.c_tts)
        self.chk_mute = QCheckBox("Тихий режим (без голосу)")
        self.chk_mute.setChecked(self.cfg.get("muted", False))
        gl_tts.addWidget(self.chk_mute)
        g_tts.setLayout(gl_tts)
        l.addWidget(g_tts)
        
        b_save = QPushButton("Зберегти налаштування")
        b_save.clicked.connect(self.save_settings)
        l.addWidget(b_save)
        l.addStretch()
        return w

    # --- Logic ---

    def switch_tab(self, index):
        for p in self.pages: p.hide()
        self.pages[index].show()
        if index == 4: self.load_notes()

    # Entries
    def refresh_entries(self):
        self.table_entries.setRowCount(0)
        for e in self.cfg.get_entries():
            r = self.table_entries.rowCount()
            self.table_entries.insertRow(r)
            self.table_entries.setItem(r, 0, QTableWidgetItem(e["id"]))
            self.table_entries.setItem(r, 1, QTableWidgetItem(e["display_name"]))
            self.table_entries.setItem(r, 2, QTableWidgetItem(", ".join(e["voice_names"])))
            self.table_entries.setItem(r, 3, QTableWidgetItem(e.get("type", "app")))
            self.table_entries.setItem(r, 4, QTableWidgetItem(e.get("path_or_url", "")))

    def add_entry(self):
        d = EntryEditDialog(parent=self)
        if d.exec():
            entries = self.cfg.get_entries()
            entries.append(d.get_data())
            self.cfg.update_entries(entries)
            self.refresh_entries()

    def edit_entry(self):
        r = self.table_entries.currentRow()
        if r < 0: return
        eid = self.table_entries.item(r, 0).text()
        entry = self.cfg.get_entry_by_id(eid)
        d = EntryEditDialog(entry, parent=self)
        if d.exec():
            entries = self.cfg.get_entries()
            for i, e in enumerate(entries):
                if e["id"] == eid: entries[i] = d.get_data()
            self.cfg.update_entries(entries)
            self.refresh_entries()

    def del_entry(self):
        r = self.table_entries.currentRow()
        if r < 0: return
        eid = self.table_entries.item(r, 0).text()
        entries = [e for e in self.cfg.get_entries() if e["id"] != eid]
        self.cfg.update_entries(entries)
        self.refresh_entries()

    # Workspaces
    def refresh_ws(self):
        self.list_ws.clear()
        for ws in self.cfg.get_workspaces():
            self.list_ws.addItem(f"{ws['display_name']} ({len(ws['steps'])} дій)")

    def add_ws(self):
        d = WorkspaceEditDialog(all_entries=self.cfg.get_entries(), parent=self)
        if d.exec():
            wss = self.cfg.get_workspaces()
            wss.append(d.get_data())
            self.cfg.update_workspaces(wss)
            self.refresh_ws()

    def edit_ws(self):
        r = self.list_ws.currentRow()
        if r < 0: return
        wss = self.cfg.get_workspaces()
        d = WorkspaceEditDialog(wss[r], all_entries=self.cfg.get_entries(), parent=self)
        if d.exec():
            wss[r] = d.get_data()
            self.cfg.update_workspaces(wss)
            self.refresh_ws()

    def del_ws(self):
        r = self.list_ws.currentRow()
        if r < 0: return
        wss = self.cfg.get_workspaces()
        del wss[r]
        self.cfg.update_workspaces(wss)
        self.refresh_ws()

    # IoT
    def refresh_iot(self):
        self.list_iot.clear()
        for dev in self.cfg.get_iot_devices():
            self.list_iot.addItem(f"{dev['display_name']} ({dev['connection_type']})")

    def add_iot(self):
        d = IoTEditDialog(parent=self)
        if d.exec():
            devs = self.cfg.get_iot_devices()
            devs.append(d.get_data())
            self.cfg.update_iot_devices(devs)
            self.refresh_iot()

    def edit_iot(self):
        r = self.list_iot.currentRow()
        if r < 0: return
        devs = self.cfg.get_iot_devices()
        d = IoTEditDialog(devs[r], parent=self)
        if d.exec():
            devs[r] = d.get_data()
            self.cfg.update_iot_devices(devs)
            self.refresh_iot()

    def del_iot(self):
        r = self.list_iot.currentRow()
        if r < 0: return
        devs = self.cfg.get_iot_devices()
        del devs[r]
        self.cfg.update_iot_devices(devs)
        self.refresh_iot()

    # Notes
    def load_notes(self):
        import glob
        path = os.path.join(os.path.expanduser("~"), "Documents", "Petrucha_Notes", "*.md")
        files = glob.glob(path)
        if not files:
            self.notes_view.setText("Немає нотаток.")
            return
        latest = max(files, key=os.path.getctime)
        with open(latest, "r", encoding="utf-8") as f:
            self.notes_view.setText(f"--- {os.path.basename(latest)} ---\n\n{f.read()}")

    # Chat & Worker
    @pyqtSlot()
    def toggle_mic(self):
        if self.btn_mic.isChecked():
            self.btn_mic.setText("Зупинити")
            self.btn_mic.setObjectName("StopBtn")
            self.btn_mic.setStyleSheet("background-color: #ef4444; border-color: #ef4444; color: white;")
            self.worker.start()
        else:
            self.btn_mic.setText("Слухати")
            self.btn_mic.setObjectName("")
            self.btn_mic.setStyleSheet("background-color: #444654; color: #ECECF1;")
            self.worker.stop_listening()

    @pyqtSlot()
    def send_msg(self):
        t = self.inp_text.text().strip()
        if t:
            self.add_user_msg(t)
            self.worker.manual_input(t)
            self.inp_text.clear()

    @pyqtSlot(str)
    def add_user_msg(self, text):
        bubble = MessageBubble(text, role="user")
        self.chat_layout.addWidget(bubble)
        self.scroll_chat()

    @pyqtSlot(str)
    def add_bot_msg(self, text):
        bubble = MessageBubble(text, role="assistant")
        self.chat_layout.addWidget(bubble)
        self.scroll_chat()

    def scroll_chat(self):
        # Scroll to bottom
        self.chat_scroll.verticalScrollBar().setValue(
            self.chat_scroll.verticalScrollBar().maximum()
        )

    @pyqtSlot(str)
    def update_status(self, text):
        self.lbl_status.setText(text)

    @pyqtSlot(int)
    def update_mic(self, level):
        self.mic_bar.setValue(level)

    def save_settings(self):
        self.cfg.set("stt_backend", self.c_stt.currentText())
        self.cfg.set("llm_backend_default", self.c_llm.currentText())
        self.cfg.set("gemini_api_key", self.i_gemini.text())
        self.cfg.set("tts_engine", self.c_tts.currentText())
        self.cfg.set("muted", self.chk_mute.isChecked())
        self.worker.update_backends()
        QMessageBox.information(self, "Налаштування", "Збережено успішно!")

def run_gui():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    w = MainWindow()
    w.show()
    sys.exit(app.exec())