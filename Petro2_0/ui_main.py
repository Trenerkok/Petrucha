import sys
import os
import uuid
import json
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QTextEdit, QLineEdit, QPushButton, QLabel, QListWidget, QListWidgetItem,
    QProgressBar, QScrollArea, QFrame, QSizePolicy, QComboBox, QCheckBox,
    QGroupBox, QTableWidget, QTableWidgetItem, QHeaderView, QDialog, QFormLayout,
    QMessageBox, QFileDialog, QStackedWidget, QSpinBox
)
from PyQt6.QtCore import Qt, pyqtSlot, QSize
from PyQt6.QtGui import QFont, QColor, QFontMetrics

from config import Config
from assistant_core import AssistantCore

# --- STYLES ---
STYLE = """
    QMainWindow { background-color: #343541; color: #ECECF1; }
    QWidget { font-family: 'Segoe UI', sans-serif; font-size: 14px; color: #ECECF1; }
    QListWidget#Sidebar { background-color: #202123; border: none; font-size: 15px; }
    QListWidget#Sidebar::item { padding: 15px; border-bottom: 1px solid #2b2c2f; }
    QListWidget#Sidebar::item:selected { background-color: #343541; border-left: 3px solid #10a37f; }
    QLineEdit, QTextEdit, QComboBox, QSpinBox { 
        background-color: #40414F; color: #ECECF1; 
        border: 1px solid #565869; border-radius: 6px; padding: 8px; 
    }
    QPushButton { 
        background-color: #444654; color: #ECECF1; 
        border: 1px solid #565869; border-radius: 5px; padding: 8px 15px; 
    }
    QPushButton:hover { background-color: #505260; }
    QPushButton#AccentBtn { background-color: #10a37f; border: none; color: white; }
    QPushButton#AccentBtn:hover { background-color: #1a7f64; }
    QPushButton#StopBtn { background-color: #ef4444; border: none; color: white; }
    QTableWidget { background-color: #202123; gridline-color: #444654; border: none; }
    QHeaderView::section { background-color: #343541; padding: 8px; border: none; }
    QGroupBox { border: 1px solid #565869; border-radius: 5px; margin-top: 20px; padding-top: 15px; }
    QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 3px; }
"""

# --- WIDGETS ---
class MessageBubble(QFrame):
    def __init__(self, text, role):
        super().__init__()
        l = QHBoxLayout(self)
        l.setContentsMargins(0,5,0,5)
        lbl = QLabel(text)
        lbl.setWordWrap(True)
        lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        font = QFont("Segoe UI", 11)
        lbl.setFont(font)
        fm = QFontMetrics(font)
        width = min(fm.horizontalAdvance(text) + 40, 600)
        lbl.setMinimumWidth(max(50, width))
        lbl.setMaximumWidth(650)
        lbl.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Preferred)
        if role == "user":
            l.addStretch()
            lbl.setStyleSheet("background-color: #444654; padding: 10px; border-radius: 10px; color: white;")
            l.addWidget(lbl)
        else:
            lbl.setStyleSheet("background-color: #202123; padding: 10px; border-radius: 10px; border: 1px solid #565869; color: white;")
            l.addWidget(lbl)
            l.addStretch()

class IoTDeviceDialog(QDialog):
    def __init__(self, data=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Налаштування пристрою")
        self.resize(600, 500)
        self.data = data or {}
        layout = QVBoxLayout(self)
        
        form = QFormLayout()
        self.inp_name = QLineEdit(self.data.get("display_name", ""))
        form.addRow("Назва:", self.inp_name)
        self.combo_type = QComboBox()
        self.combo_type.addItems(["HTTP", "Serial", "MQTT"])
        self.combo_type.setCurrentText(self.data.get("connection_type", "HTTP"))
        self.combo_type.currentTextChanged.connect(self.on_type_changed)
        form.addRow("Тип:", self.combo_type)
        layout.addLayout(form)
        
        self.stack_params = QStackedWidget()
        # HTTP
        pg_http = QWidget()
        l_http = QFormLayout(pg_http)
        self.inp_http_url = QLineEdit()
        self.inp_http_method = QComboBox()
        self.inp_http_method.addItems(["GET", "POST"])
        l_http.addRow("URL:", self.inp_http_url)
        l_http.addRow("Method:", self.inp_http_method)
        self.stack_params.addWidget(pg_http)
        # Serial
        pg_serial = QWidget()
        l_serial = QFormLayout(pg_serial)
        self.inp_serial_port = QLineEdit("COM3")
        self.inp_serial_baud = QSpinBox()
        self.inp_serial_baud.setRange(300, 115200)
        self.inp_serial_baud.setValue(9600)
        l_serial.addRow("Port:", self.inp_serial_port)
        l_serial.addRow("Baudrate:", self.inp_serial_baud)
        self.stack_params.addWidget(pg_serial)
        # MQTT
        pg_mqtt = QWidget()
        l_mqtt = QFormLayout(pg_mqtt)
        self.inp_mqtt_broker = QLineEdit("localhost")
        self.inp_mqtt_topic = QLineEdit("home/device")
        l_mqtt.addRow("Broker:", self.inp_mqtt_broker)
        l_mqtt.addRow("Topic:", self.inp_mqtt_topic)
        self.stack_params.addWidget(pg_mqtt)
        
        layout.addWidget(self.stack_params)
        self.load_params()
        
        layout.addWidget(QLabel("Команди (Дії):"))
        self.list_actions = QListWidget()
        for act in self.data.get("actions", []):
            self.add_action_item(act)
        layout.addWidget(self.list_actions)
        
        h_act = QHBoxLayout()
        b_add_act = QPushButton("+ Дія")
        b_add_act.clicked.connect(self.add_action_dialog)
        b_del_act = QPushButton("-")
        b_del_act.clicked.connect(lambda: self.list_actions.takeItem(self.list_actions.currentRow()))
        h_act.addWidget(b_add_act)
        h_act.addWidget(b_del_act)
        layout.addLayout(h_act)
        
        b_save = QPushButton("Зберегти пристрій")
        b_save.setObjectName("AccentBtn")
        b_save.clicked.connect(self.accept)
        layout.addWidget(b_save)

    def on_type_changed(self, txt):
        if txt == "HTTP": self.stack_params.setCurrentIndex(0)
        elif txt == "Serial": self.stack_params.setCurrentIndex(1)
        elif txt == "MQTT": self.stack_params.setCurrentIndex(2)

    def load_params(self):
        p = self.data.get("connection_params", {})
        t = self.data.get("connection_type", "HTTP")
        if t == "HTTP":
            self.inp_http_url.setText(p.get("url", ""))
            self.inp_http_method.setCurrentText(p.get("method", "GET"))
            self.stack_params.setCurrentIndex(0)
        elif t == "Serial":
            self.inp_serial_port.setText(p.get("port", "COM3"))
            self.inp_serial_baud.setValue(int(p.get("baudrate", 9600)))
            self.stack_params.setCurrentIndex(1)
        elif t == "MQTT":
            self.inp_mqtt_broker.setText(p.get("broker", ""))
            self.inp_mqtt_topic.setText(p.get("topic", ""))
            self.stack_params.setCurrentIndex(2)

    def add_action_item(self, act):
        item = QListWidgetItem(f"{act['name']} ({act['voice_phrases'][0] if act['voice_phrases'] else ''})")
        item.setData(Qt.ItemDataRole.UserRole, act)
        self.list_actions.addItem(item)

    def add_action_dialog(self):
        d = QDialog(self)
        l = QFormLayout(d)
        i_name = QLineEdit()
        i_voice = QLineEdit()
        i_pay = QLineEdit()
        l.addRow("Назва (ID):", i_name)
        l.addRow("Фрази (через кому):", i_voice)
        l.addRow("Payload/Cmd:", i_pay)
        b = QPushButton("OK")
        b.clicked.connect(d.accept)
        l.addRow(b)
        if d.exec():
            self.add_action_item({
                "name": i_name.text(),
                "voice_phrases": [x.strip() for x in i_voice.text().split(",")],
                "payload": i_pay.text()
            })

    def get_data(self):
        ctype = self.combo_type.currentText()
        params = {}
        if ctype == "HTTP":
            params = {"url": self.inp_http_url.text(), "method": self.inp_http_method.currentText()}
        elif ctype == "Serial":
            params = {"port": self.inp_serial_port.text(), "baudrate": self.inp_serial_baud.value()}
        elif ctype == "MQTT":
            params = {"broker": self.inp_mqtt_broker.text(), "topic": self.inp_mqtt_topic.text()}
        actions = []
        for i in range(self.list_actions.count()):
            actions.append(self.list_actions.item(i).data(Qt.ItemDataRole.UserRole))
        return {
            "id": self.data.get("id", str(uuid.uuid4())[:8]),
            "display_name": self.inp_name.text(),
            "connection_type": ctype,
            "connection_params": params,
            "actions": actions
        }

class EditEntryDialog(QDialog):
    def __init__(self, data=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Редагування запису")
        self.resize(500, 350)
        self.data = data or {}
        l = QFormLayout(self)
        self.inp_name = QLineEdit(self.data.get("name", ""))
        l.addRow("Назва (для вас):", self.inp_name)
        self.inp_voice = QLineEdit(", ".join(self.data.get("voice_phrases", [])))
        self.inp_voice.setPlaceholderText("steam, стім, іграшка")
        l.addRow("Як звертатися голосом:", self.inp_voice)
        self.combo_type = QComboBox()
        self.combo_type.addItems(["app", "website", "folder", "file"])
        self.combo_type.setCurrentText(self.data.get("type", "app"))
        l.addRow("Що це:", self.combo_type)
        path_box = QHBoxLayout()
        self.inp_path = QLineEdit(self.data.get("path", ""))
        path_box.addWidget(self.inp_path)
        b_browse = QPushButton("...")
        b_browse.clicked.connect(self.browse)
        path_box.addWidget(b_browse)
        l.addRow("Шлях / Посилання:", path_box)
        btn_save = QPushButton("Зберегти")
        btn_save.setObjectName("AccentBtn")
        btn_save.clicked.connect(self.accept)
        l.addRow(btn_save)

    def browse(self):
        t = self.combo_type.currentText()
        if t == "folder":
            r = QFileDialog.getExistingDirectory(self, "Обрати папку")
            if r: self.inp_path.setText(r)
        elif t != "website":
            r, _ = QFileDialog.getOpenFileName(self, "Обрати файл")
            if r: self.inp_path.setText(r)

    def get_data(self):
        return {
            "id": self.data.get("id", str(uuid.uuid4())[:8]),
            "name": self.inp_name.text().strip(),
            "voice_phrases": [x.strip() for x in self.inp_voice.text().split(",") if x.strip()],
            "type": self.combo_type.currentText(),
            "path": self.inp_path.text().strip()
        }

class EditWorkspaceDialog(QDialog):
    def __init__(self, ws=None, entries=[], iot=[], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Редагувати Протокол")
        self.resize(600, 500)
        self.data = ws or {}
        self.entries = entries
        self.iot = iot
        l = QVBoxLayout(self)
        form = QFormLayout()
        self.inp_name = QLineEdit(self.data.get("name", ""))
        form.addRow("Назва протоколу:", self.inp_name)
        self.inp_voice = QLineEdit(", ".join(self.data.get("voice_phrases", [])))
        form.addRow("Голосові фрази:", self.inp_voice)
        l.addLayout(form)
        l.addWidget(QLabel("Кроки:"))
        self.list_steps = QListWidget()
        for step in self.data.get("steps", []):
            self.add_step_ui(step)
        l.addWidget(self.list_steps)
        hbox = QHBoxLayout()
        b_add = QPushButton("+ Додати дію")
        b_add.clicked.connect(self.add_step_dialog)
        b_del = QPushButton("× Видалити")
        b_del.clicked.connect(lambda: self.list_steps.takeItem(self.list_steps.currentRow()))
        hbox.addWidget(b_add)
        hbox.addWidget(b_del)
        l.addLayout(hbox)
        b_save = QPushButton("Зберегти")
        b_save.setObjectName("AccentBtn")
        b_save.clicked.connect(self.accept)
        l.addWidget(b_save)

    def add_step_ui(self, step):
        txt = f"{step['action']}"
        if "target_id" in step: txt += f" -> {step['target_id']}"
        if "subaction" in step: txt += f" -> {step['subaction']}"
        if "url" in step: txt += f" -> {step['url']}"
        item = QListWidgetItem(txt)
        item.setData(Qt.ItemDataRole.UserRole, step)
        self.list_steps.addItem(item)

    def add_step_dialog(self):
        d = QDialog(self)
        l = QFormLayout(d)
        c_act = QComboBox()
        c_act.addItems(["OPEN_ENTRY", "CLOSE_APP", "OPEN_WEBSITE", "MEDIA", "WINDOW", "WAIT", "IOT"])
        l.addRow("Дія:", c_act)
        c_entry = QComboBox()
        c_entry.addItems([e["id"] for e in self.entries])
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
            if act in ["OPEN_ENTRY", "CLOSE_APP"]: step["target_id"] = c_entry.currentText()
            elif act == "OPEN_WEBSITE": step["url"] = i_param.text()
            elif act in ["MEDIA", "WINDOW"]: step["subaction"] = i_param.text()
            elif act == "WAIT": step["value"] = i_param.text()
            self.add_step_ui(step)

    def get_data(self):
        steps = []
        for i in range(self.list_steps.count()):
            steps.append(self.list_steps.item(i).data(Qt.ItemDataRole.UserRole))
        return {
            "id": self.data.get("id", str(uuid.uuid4())[:8]),
            "name": self.inp_name.text(),
            "voice_phrases": [x.strip() for x in self.inp_voice.text().split(",") if x.strip()],
            "steps": steps
        }

# --- MAIN UI ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Petrucha Assistant")
        self.resize(1200, 800)
        self.cfg = Config()
        self.core = AssistantCore()
        self.core.sig_user_text.connect(self.add_user_msg)
        self.core.sig_bot_text.connect(self.add_bot_msg)
        self.core.sig_status.connect(self.set_status)
        self.core.sig_mic_level.connect(self.set_mic)
        self.core.sig_timer_update.connect(self.update_timer)
        self.init_ui()

    def init_ui(self):
        self.setStyleSheet(STYLE)
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        self.sidebar = QListWidget()
        self.sidebar.setObjectName("Sidebar")
        self.sidebar.setFixedWidth(230)
        self.sidebar.addItems(["Головне", "Програми", "Протоколи", "IoT-пристрої", "Нотатки", "Довідка", "Налаштування"])
        self.sidebar.currentRowChanged.connect(self.switch_tab)
        layout.addWidget(self.sidebar)
        self.content_area = QWidget()
        self.content_layout = QVBoxLayout(self.content_area)
        self.content_layout.setContentsMargins(20, 20, 20, 20)
        layout.addWidget(self.content_area)
        self.pages = [
            self.create_chat_tab(),
            self.create_entries_tab(),
            self.create_workspaces_tab(),
            self.create_iot_tab(),
            self.create_notes_tab(),
            self.create_guide_tab(),
            self.create_settings_tab()
        ]
        for p in self.pages: 
            self.content_layout.addWidget(p)
            p.hide()
        self.sidebar.setCurrentRow(0)

    def switch_tab(self, idx):
        for i, p in enumerate(self.pages): p.setVisible(i == idx)
        if idx == 4: self.refresh_notes()

    def create_chat_tab(self):
        w = QWidget()
        l = QVBoxLayout(w)
        head = QHBoxLayout()
        head.addWidget(QLabel("<h2>Головне</h2>"))
        head.addStretch()
        self.lbl_timer = QLabel("")
        self.lbl_timer.setStyleSheet("color: #ffcc00; font-weight: bold; font-size: 18px;")
        head.addWidget(self.lbl_timer)
        head.addSpacing(20)
        self.status_lbl = QLabel("Очікую")
        self.status_lbl.setStyleSheet("color: #8e8ea0;")
        head.addWidget(self.status_lbl)
        l.addLayout(head)
        self.chat_scroll = QScrollArea()
        self.chat_scroll.setWidgetResizable(True)
        self.chat_content = QWidget()
        self.chat_layout = QVBoxLayout(self.chat_content)
        self.chat_layout.addStretch()
        self.chat_scroll.setWidget(self.chat_content)
        l.addWidget(self.chat_scroll)
        self.mic_bar = QProgressBar()
        self.mic_bar.setFixedHeight(4)
        self.mic_bar.setTextVisible(False)
        l.addWidget(self.mic_bar)
        hbox = QHBoxLayout()
        self.btn_mic = QPushButton("Слухати")
        self.btn_mic.setCheckable(True)
        self.btn_mic.clicked.connect(self.toggle_mic)
        hbox.addWidget(self.btn_mic)
        self.inp_msg = QLineEdit()
        self.inp_msg.setPlaceholderText("Напишіть повідомлення...")
        self.inp_msg.returnPressed.connect(self.send_msg)
        hbox.addWidget(self.inp_msg)
        b_send = QPushButton("Надіслати")
        b_send.setObjectName("AccentBtn")
        b_send.clicked.connect(self.send_msg)
        hbox.addWidget(b_send)
        l.addLayout(hbox)
        return w

    def create_entries_tab(self):
        w = QWidget()
        l = QVBoxLayout(w)
        l.addWidget(QLabel("<h2>Програми та файли</h2>"))
        l.addWidget(QLabel("Додайте сюди програми або сайти, щоб відкривати їх голосом."))
        self.table_entries = QTableWidget(0, 4)
        self.table_entries.setHorizontalHeaderLabels(["Назва", "Голос", "Тип", "Шлях"])
        self.table_entries.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        l.addWidget(self.table_entries)
        hbox = QHBoxLayout()
        b_add = QPushButton("+ Додати")
        b_add.setObjectName("AccentBtn")
        b_add.clicked.connect(self.add_entry)
        b_del = QPushButton("Видалити")
        b_del.clicked.connect(self.del_entry)
        hbox.addWidget(b_add)
        hbox.addWidget(b_del)
        l.addLayout(hbox)
        self.refresh_entries()
        return w

    def create_workspaces_tab(self):
        w = QWidget()
        l = QVBoxLayout(w)
        l.addWidget(QLabel("<h2>Протоколи (Сценарії)</h2>"))
        l.addWidget(QLabel("Налаштування послідовності дій для однієї команди."))
        self.list_ws = QListWidget()
        l.addWidget(self.list_ws)
        hbox = QHBoxLayout()
        b_add = QPushButton("+ Протокол")
        b_add.setObjectName("AccentBtn")
        b_add.clicked.connect(self.add_ws)
        b_del = QPushButton("Видалити")
        b_del.clicked.connect(self.del_ws)
        hbox.addWidget(b_add)
        hbox.addWidget(b_del)
        l.addLayout(hbox)
        self.refresh_ws()
        return w

    def create_iot_tab(self):
        w = QWidget()
        l = QVBoxLayout(w)
        l.addWidget(QLabel("<h2>IoT Пристрої</h2>"))
        l.addWidget(QLabel("Додавайте лампи, реле та Arduino тут."))
        self.list_iot = QListWidget()
        l.addWidget(self.list_iot)
        hbox = QHBoxLayout()
        b_add = QPushButton("+ Пристрій")
        b_add.setObjectName("AccentBtn")
        b_add.clicked.connect(self.add_iot)
        b_edit = QPushButton("Редагувати")
        b_edit.clicked.connect(self.edit_iot)
        b_del = QPushButton("Видалити")
        b_del.clicked.connect(self.del_iot)
        hbox.addWidget(b_add)
        hbox.addWidget(b_edit)
        hbox.addWidget(b_del)
        l.addLayout(hbox)
        self.refresh_iot()
        return w

    def create_notes_tab(self):
        w = QWidget()
        l = QVBoxLayout(w)
        l.addWidget(QLabel("<h2>Нотатки</h2>"))
        self.txt_note = QTextEdit()
        self.txt_note.setReadOnly(True)
        l.addWidget(self.txt_note)
        return w

    def create_guide_tab(self):
        w = QWidget()
        l = QVBoxLayout(w)
        l.addWidget(QLabel("<h2>Довідка користувача</h2>"))
        text = QTextEdit()
        text.setReadOnly(True)
        html = """
        <h3>Основні можливості</h3>
        <ul>
            <li><b>Керування ПК:</b> "Відкрий стім", "Закрий браузер", "Згорни вікна".</li>
            <li><b>Пошук:</b> "Знайди в інтернеті погоду на завтра", "Хто такий Ілон Маск".</li>
            <li><b>Протоколи:</b> Створюйте сценарії (напр. "Робочий режим"), які відкривають сайти та програми разом.</li>
            <li><b>IoT:</b> Керування Arduino/ESP через HTTP/Serial ("Увімкни лампу").</li>
            <li><b>Зір (Vision):</b> "Що ти бачиш на екрані?" (потрібен Gemini Key).</li>
            <li><b>Пам'ять:</b> "Запам'ятай код 1234".</li>
        </ul>
        <h3>Довідка</h3>
        <p>Спробуйте сказати: <b>"Що ти вмієш?"</b> або <b>"Як ти працюєш?"</b> для демонстрації архітектури.</p>
        """
        text.setHtml(html)
        l.addWidget(text)
        return w

    def create_settings_tab(self):
        w = QWidget()
        l = QVBoxLayout(w)
        l.addWidget(QLabel("<h2>Налаштування</h2>"))
        g = QGroupBox("Параметри")
        fl = QFormLayout(g)
        self.c_stt = QComboBox()
        self.c_stt.addItems(["vosk", "online"])
        self.c_stt.setCurrentText(self.cfg.get("stt_backend"))
        fl.addRow("STT:", self.c_stt)
        self.c_tts = QComboBox()
        self.c_tts.addItems(["silero", "gtts", "pyttsx3"])
        self.c_tts.setCurrentText(self.cfg.get("tts_engine"))
        fl.addRow("Голос (TTS):", self.c_tts)
        self.c_llm = QComboBox()
        self.c_llm.addItems(["local", "gemini"])
        self.c_llm.setCurrentText(self.cfg.get("llm_backend"))
        fl.addRow("LLM:", self.c_llm)
        self.chk_wake = QCheckBox("Wake Word ('Петро')")
        self.chk_wake.setChecked(self.cfg.get("wake_word_enabled", True))
        fl.addRow("Активація:", self.chk_wake)
        self.i_key = QLineEdit(self.cfg.get("gemini_key"))
        self.i_key.setEchoMode(QLineEdit.EchoMode.Password)
        fl.addRow("Gemini Key:", self.i_key)
        l.addWidget(g)
        b_save = QPushButton("Зберегти")
        b_save.setObjectName("AccentBtn")
        b_save.clicked.connect(self.save_settings)
        l.addWidget(b_save)
        l.addStretch()
        return w

    # --- Logic ---
    def refresh_entries(self):
        self.table_entries.setRowCount(0)
        for e in self.cfg.get_entries():
            r = self.table_entries.rowCount()
            self.table_entries.insertRow(r)
            self.table_entries.setItem(r, 0, QTableWidgetItem(e.get("name","")))
            self.table_entries.setItem(r, 1, QTableWidgetItem(",".join(e.get("voice_phrases",[]))))
            self.table_entries.setItem(r, 2, QTableWidgetItem(e.get("type","")))
            self.table_entries.setItem(r, 3, QTableWidgetItem(e.get("path","")))

    def add_entry(self):
        d = EditEntryDialog(parent=self)
        if d.exec():
            entries = self.cfg.get_entries()
            entries.append(d.get_data())
            self.cfg.update_entries(entries)
            self.refresh_entries()

    def del_entry(self):
        r = self.table_entries.currentRow()
        if r >= 0:
            entries = self.cfg.get_entries()
            del entries[r]
            self.cfg.update_entries(entries)
            self.refresh_entries()

    def refresh_ws(self):
        self.list_ws.clear()
        for w in self.cfg.get_workspaces():
            self.list_ws.addItem(f"{w['name']}")

    def add_ws(self):
        d = EditWorkspaceDialog(entries=self.cfg.get_entries(), parent=self)
        if d.exec():
            ws = self.cfg.get_workspaces()
            ws.append(d.get_data())
            self.cfg.update_workspaces(ws)
            self.refresh_ws()

    def del_ws(self):
        r = self.list_ws.currentRow()
        if r >= 0:
            ws = self.cfg.get_workspaces()
            del ws[r]
            self.cfg.update_workspaces(ws)
            self.refresh_ws()

    def refresh_iot(self):
        self.list_iot.clear()
        for d in self.cfg.get_iot_devices():
            self.list_iot.addItem(f"{d['display_name']} ({d['connection_type']})")

    def add_iot(self):
        d = IoTDeviceDialog(parent=self)
        if d.exec():
            devs = self.cfg.get_iot_devices()
            devs.append(d.get_data())
            self.cfg.update_iot_devices(devs)
            self.refresh_iot()

    def edit_iot(self):
        r = self.list_iot.currentRow()
        if r < 0: return
        devs = self.cfg.get_iot_devices()
        d = IoTDeviceDialog(devs[r], parent=self)
        if d.exec():
            devs[r] = d.get_data()
            self.cfg.update_iot_devices(devs)
            self.refresh_iot()

    def del_iot(self):
        r = self.list_iot.currentRow()
        if r >= 0:
            devs = self.cfg.get_iot_devices()
            del devs[r]
            self.cfg.update_iot_devices(devs)
            self.refresh_iot()

    def refresh_notes(self):
        notes = self.core.sys.get_notes_list()
        if notes: self.txt_note.setText(self.core.sys.read_note(notes[0]))
        else: self.txt_note.setText("Немає нотаток.")

    @pyqtSlot()
    def toggle_mic(self):
        if self.btn_mic.isChecked():
            self.btn_mic.setText("Зупинити")
            self.btn_mic.setObjectName("StopBtn")
            self.btn_mic.setStyleSheet("background-color: #ef4444;")
            self.core.start_listening()
        else:
            self.btn_mic.setText("Слухати")
            self.btn_mic.setObjectName("")
            self.btn_mic.setStyleSheet("background-color: #444654;")
            self.core.stop_listening()

    @pyqtSlot()
    def send_msg(self):
        t = self.inp_msg.text().strip()
        if t:
            self.core.manual_input(t)
            self.inp_msg.clear()

    @pyqtSlot(str)
    def add_user_msg(self, text):
        self.chat_layout.addWidget(MessageBubble(text, "user"))
        self.scroll_chat()

    @pyqtSlot(str)
    def add_bot_msg(self, text):
        self.chat_layout.addWidget(MessageBubble(text, "bot"))
        self.scroll_chat()

    def scroll_chat(self):
        self.chat_scroll.verticalScrollBar().setValue(self.chat_scroll.verticalScrollBar().maximum())

    @pyqtSlot(str)
    def set_status(self, t): self.status_lbl.setText(t)
    @pyqtSlot(int)
    def set_mic(self, v): self.mic_bar.setValue(v)
    @pyqtSlot(str)
    def update_timer(self, t): self.lbl_timer.setText(t)

    def save_settings(self):
        self.cfg.set("stt_backend", self.c_stt.currentText())
        self.cfg.set("tts_engine", self.c_tts.currentText())
        self.cfg.set("llm_backend", self.c_llm.currentText())
        self.cfg.set("gemini_key", self.i_key.text())
        self.cfg.set("wake_word_enabled", self.chk_wake.isChecked())
        self.core.tts = self.core.tts.__class__(self.cfg) # Re-init TTS
        QMessageBox.information(self, "Info", "Saved")