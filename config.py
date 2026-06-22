import os
from dotenv import load_dotenv

load_dotenv()

SERVICE_TOKEN = os.getenv("SERVICE_TOKEN", "dev-token-123")
PORT = int(os.getenv("PORT", 8001))
GLOBAL_MEDIA_PATH = "/home/adminstudent/media"

USE_YANDEX = os.getenv("USE_YANDEX", "False").lower() in ("true", "1", "yes")
YC_FOLDER_ID = os.getenv("YC_FOLDER_ID", "")
YC_API_KEY = os.getenv("YC_API_KEY", "")
UNSPLASH_ACCESS_KEY = os.getenv("UNSPLASH_ACCESS_KEY", "")
