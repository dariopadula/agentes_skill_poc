from pathlib import Path

from dotenv import load_dotenv


PROJECT_DIR = Path(__file__).resolve().parent
ENV_PATH = PROJECT_DIR.parent / ".env"


def load_environment() -> Path:
    """Carga el .env de la carpeta padre sin sobrescribir variables existentes."""
    load_dotenv(dotenv_path=ENV_PATH, override=False)
    return ENV_PATH
