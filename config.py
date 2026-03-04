import os

class Config:
    SECRET_KEY = "gruha_alankara_secret"

    BASE_DIR = os.path.abspath(os.path.dirname(__file__))

    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(BASE_DIR, "database", "designs.db")

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    UPLOAD_FOLDER = "uploads"
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024