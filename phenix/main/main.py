import sys
import os
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

# Ensure the script directory is in the path
os.chdir(os.path.dirname(os.path.abspath(__file__)))


def main():
    print("======================================")
    print(" PETRUCHA AI Assistant (PyQt6)")
    print("======================================")

    try:
        from gui import run_gui
        run_gui()
    except ImportError as e:
        print(f"Critical Error: Failed to import GUI module. {e}")
        print("Please ensure all requirements are installed:")
        print("pip install -r requirements.txt")
    except Exception as e:
        print(f"Unexpected Error: {e}")


if __name__ == "__main__":
    main()
