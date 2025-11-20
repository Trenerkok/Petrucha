import sys
import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
import logging
from PyQt6.QtWidgets import QApplication

# Забезпечуємо, що робоча папка - це папка скрипта
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# --- НАЛАШТУВАННЯ ЛОГУВАННЯ ---
def setup_logging():
    # Формат: Час - Файл - Рівень - Повідомлення
    log_format = '%(asctime)s - [%(filename)s:%(lineno)d] - %(levelname)s - %(message)s'
    
    logging.basicConfig(
        level=logging.DEBUG,  # DEBUG показує ВСЕ. Змініть на INFO, щоб бачити менше.
        format=log_format,
        handlers=[
            logging.FileHandler("petrucha.log", encoding='utf-8'), # Запис у файл
            logging.StreamHandler() # Вивід у консоль
        ]
    )
    logging.info("=== ЗАПУСК PETRUCHA ASSISTANT ===")

if __name__ == "__main__":
    setup_logging()
    
    print("Starting Petrucha Rebuilt...")
    try:
        # Імпортуємо клас головного вікна
        from ui_main import MainWindow
        
        app = QApplication(sys.argv)
        app.setStyle("Fusion")
        
        w = MainWindow()
        w.show()
        
        logging.info("Інтерфейс ініціалізовано успішно")
        sys.exit(app.exec())
        
    except ImportError as e:
        logging.critical(f"CRITICAL IMPORT ERROR: {e}")
        print(f"Critical Error: {e}")
        print("ПОРАДА: Перевірте, чи існує файл ui_main.py поруч.")
    except Exception as e:
        logging.critical(f"UNEXPECTED CRASH: {e}", exc_info=True)
        print(f"Unexpected Error: {e}")
        import traceback
        traceback.print_exc()