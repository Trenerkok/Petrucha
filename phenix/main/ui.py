import tkinter as tk
from tkinter import ttk

# Глобальні посилання на елементи UI
_root: tk.Tk | None = None
_chat_text: tk.Text | None = None
_input_entry: tk.Entry | None = None

_status_labels = {
    "muted": None,
    "mic": None,
    "llm": None,
}

_callbacks = {
    "send": None,
    "mute": None,
    "mic": None,
}

# Збережений стан, якщо ui_set_status викликається до старту UI
_state_cache = {
    "muted": False,
    "mic_on": True,
    "llm_mode": "local",
}


# -------------------------- API --------------------------


def ui_add_message(role: str, text: str) -> None:
    """
    Додає повідомлення в чат.
    role: "user" | "assistant" | будь-що ще.
    """
    global _chat_text, _root
    prefix = ""
    if role == "user":
        prefix = "Ти: "
    elif role == "assistant":
        prefix = "Петруча: "
    else:
        prefix = ""

    line = prefix + text + "\n"

    if _chat_text is None:
        # UI ще не ініціалізований — нічого не робимо
        return

    _chat_text.configure(state="normal")
    _chat_text.insert("end", line)
    _chat_text.see("end")
    _chat_text.configure(state="disabled")

    if _root is not None:
        _root.update_idletasks()


def ui_set_status(muted: bool | None = None,
                  mic_on: bool | None = None,
                  llm_mode: str | None = None) -> None:
    """
    Оновлює статуси (Mute / Mic / LLM mode).
    Може викликатися ДО start_ui — тоді просто кешує стан.
    """
    global _status_labels, _state_cache

    if muted is not None:
        _state_cache["muted"] = muted
    if mic_on is not None:
        _state_cache["mic_on"] = mic_on
    if llm_mode is not None:
        _state_cache["llm_mode"] = llm_mode

    # Якщо UI ще нема — вийти
    if _status_labels["muted"] is None:
        return

    # Оновлюємо підписи, використовуючи кеш
    m = _state_cache["muted"]
    mc = _state_cache["mic_on"]
    lm = _state_cache["llm_mode"]

    _status_labels["muted"].config(
        text=f"Mute: {'ON' if m else 'OFF'}",
        foreground="#ff5555" if m else "#50fa7b",
    )
    _status_labels["mic"].config(
        text=f"Mic: {'ON' if mc else 'OFF'}",
        foreground="#50fa7b" if mc else "#ff5555",
    )
    _status_labels["llm"].config(
        text=f"LLM: {lm.upper()}",
        foreground="#8be9fd",
    )


# -------------------------- ВНУТРІШНІ ФУНКЦІЇ --------------------------


def _build_style(root: tk.Tk) -> None:
    """
    Налаштування темної теми (простий кастом через ttk.Style).
    """
    style = ttk.Style(root)

    # Спробувати use 'clam' — він краще тримає кастомні кольори
    try:
        style.theme_use("clam")
    except Exception:
        pass

    bg = "#1e1f29"
    bg_alt = "#282a36"
    fg = "#f8f8f2"
    accent = "#bd93f9"

    root.configure(bg=bg)

    style.configure(".", background=bg, foreground=fg, fieldbackground=bg_alt)

    style.configure(
        "Header.TLabel",
        background=bg,
        foreground=fg,
        font=("Segoe UI", 14, "bold"),
    )
    style.configure(
        "SubHeader.TLabel",
        background=bg,
        foreground="#bbbbbb",
        font=("Segoe UI", 9),
    )

    style.configure(
        "Chat.TFrame",
        background=bg_alt,
    )
    style.configure(
        "TButton",
        padding=5,
        background=bg_alt,
        foreground=fg,
        relief="flat",
    )
    style.map(
        "TButton",
        background=[("active", accent)],
        foreground=[("active", "#ffffff")],
    )


def _on_send_clicked(event=None):
    """
    Обробник кнопки «Надіслати» та клавіші Enter.
    """
    global _input_entry, _callbacks

    if _input_entry is None:
        return
    text = _input_entry.get().strip()
    if not text:
        return

    _input_entry.delete(0, "end")

    cb = _callbacks.get("send")
    if cb is not None:
        cb(text)


def _on_mute_clicked():
    cb = _callbacks.get("mute")
    if cb is not None:
        cb()


def _on_mic_clicked():
    cb = _callbacks.get("mic")
    if cb is not None:
        cb()


# -------------------------- ГОЛОВНА ФУНКЦІЯ СТАРТУ UI --------------------------


def start_ui(on_send_text, on_toggle_mute, on_toggle_mic) -> None:
    """
    Стартує вікно з чат-інтерфейсом у стилі ChatGPT:
    - великий read-only чат;
    - однорядкове активне поле вводу внизу;
    - кнопки Mic/Mute і статус-бар.
    Ця функція блокує потік (mainloop) — її треба викликати з головного потоку.
    """
    global _root, _chat_text, _input_entry, _status_labels, _callbacks

    _callbacks["send"] = on_send_text
    _callbacks["mute"] = on_toggle_mute
    _callbacks["mic"] = on_toggle_mic

    root = tk.Tk()
    _root = root
    root.title("PETRUCHA · Voice Assistant (IoT-compatible)")
    root.geometry("900x600")
    root.minsize(800, 500)

    _build_style(root)

    bg = "#1e1f29"
    bg_alt = "#282a36"
    fg = "#f8f8f2"

    # --------- Верхній блок (заголовок) ---------
    header_frame = ttk.Frame(root)
    header_frame.pack(side="top", fill="x", padx=10, pady=(10, 5))

    title_lbl = ttk.Label(
        header_frame,
        text="PETRUCHA · Voice Assistant (IoT-compatible)",
        style="Header.TLabel",
    )
    title_lbl.pack(anchor="w")

    subtitle_lbl = ttk.Label(
        header_frame,
        text="Україномовний асистент керування ПК, пошуку та сумісний з IoT",
        style="SubHeader.TLabel",
    )
    subtitle_lbl.pack(anchor="w")

    # --------- Центральна частина: чат + правий статус/лог (опційно) ---------
    center_frame = ttk.Frame(root)
    center_frame.pack(side="top", fill="both", expand=True, padx=10, pady=5)

    # Ліва частина — чат
    chat_frame = ttk.Frame(center_frame, style="Chat.TFrame")
    chat_frame.pack(side="left", fill="both", expand=True)

    chat_text = tk.Text(
        chat_frame,
        wrap="word",
        bg=bg_alt,
        fg=fg,
        insertbackground=fg,
        relief="flat",
        state="disabled",
    )
    chat_text.pack(side="left", fill="both", expand=True, padx=(0, 5), pady=5)

    scrollbar = ttk.Scrollbar(chat_frame, command=chat_text.yview)
    scrollbar.pack(side="right", fill="y")
    chat_text.configure(yscrollcommand=scrollbar.set)

    _chat_text = chat_text

    # Права частина — невелика панель для логів/підказок (простий варіант)
    side_frame = ttk.Frame(center_frame)
    side_frame.pack(side="right", fill="y")

    side_label = ttk.Label(
        side_frame,
        text="Підказки / лог (спрощено)",
        style="SubHeader.TLabel",
    )
    side_label.pack(anchor="w", pady=(5, 2))

    tips = tk.Text(
        side_frame,
        height=10,
        width=32,
        bg=bg_alt,
        fg="#bbbbbb",
        wrap="word",
        relief="flat",
        state="disabled",
    )
    tips.pack(fill="both", expand=False, pady=5)

    tips.configure(state="normal")
    tips.insert(
        "end",
        "Приклади:\n"
        "• «петро котра година»\n"
        "• «петруча відкрий телеграм»\n"
        "• «петро загугли що таке дуб»\n"
        "• «петро режим джеміні»\n"
        "• «петро вимкни комп'ютер» (потребує підтвердження)\n",
    )
    tips.configure(state="disabled")

    # --------- Нижній блок: поле вводу + кнопки ---------
    bottom_frame = ttk.Frame(root)
    bottom_frame.pack(side="bottom", fill="x", padx=10, pady=(0, 10))

    # Статус-бар
    status_frame = ttk.Frame(bottom_frame)
    status_frame.pack(side="top", fill="x", pady=(0, 5))

    lbl_muted = ttk.Label(status_frame, text="Mute: OFF")
    lbl_muted.pack(side="left", padx=(0, 15))

    lbl_mic = ttk.Label(status_frame, text="Mic: ON")
    lbl_mic.pack(side="left", padx=(0, 15))

    lbl_llm = ttk.Label(status_frame, text="LLM: LOCAL")
    lbl_llm.pack(side="left", padx=(0, 15))

    _status_labels["muted"] = lbl_muted
    _status_labels["mic"] = lbl_mic
    _status_labels["llm"] = lbl_llm

    # Кнопки керування праворуч
    buttons_frame = ttk.Frame(status_frame)
    buttons_frame.pack(side="right")

    btn_mic = ttk.Button(buttons_frame, text="Mic", command=_on_mic_clicked)
    btn_mic.pack(side="right", padx=5)

    btn_mute = ttk.Button(buttons_frame, text="Mute", command=_on_mute_clicked)
    btn_mute.pack(side="right", padx=5)

    # Поле вводу + кнопка "Надіслати"
    input_frame = ttk.Frame(bottom_frame)
    input_frame.pack(side="top", fill="x")

    input_entry = tk.Entry(
        input_frame,
        bg=bg_alt,
        fg=fg,
        insertbackground=fg,
        relief="flat",
        font=("Segoe UI", 10),
    )
    input_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))
    _input_entry = input_entry

    # ВАЖЛИВО: поле активне, НІЯКОГО state="disabled"
    input_entry.focus_set()

    btn_send = ttk.Button(input_frame, text="Надіслати", command=_on_send_clicked)
    btn_send.pack(side="right")

    # Enter у полі вводу = надіслати
    input_entry.bind("<Return>", _on_send_clicked)

    # Після створення всіх елементів — застосувати кешований статус
    ui_set_status()  # підтягне стан з _state_cache

    # Невелике вітальне повідомлення в чат
    ui_add_message(
        "assistant",
        "Привіт! Я Петруча. Я слухаю тебе голосом або через це поле вводу.",
    )

    root.mainloop()
