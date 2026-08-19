import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
print(os.environ.get('DATABASE_URL'))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-fallback-key')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'postgresql://sgide_user:sgide_pass_2024@localhost:5432/inventario_escolar')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Use /uploads in Docker (to avoid reloader), or local 'uploads' if running directly
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'uploads'))
    TEMPLATES_WORD_FOLDER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'templates_word')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max upload
    # Año actual para estructurar las carpetas de documentos por año
    ANIO_ACTUAL = os.environ.get('ANIO_ACTUAL', datetime.now().year)
