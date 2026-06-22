from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from routers.generate import router as generate_router
from models import HealthResponse
from config import PORT

app = FastAPI(title="AI-PresentEd Generation Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MEDIA_PATH = os.path.join(BASE_DIR, "media")

if not os.path.exists(MEDIA_PATH):
    os.makedirs(MEDIA_PATH)

app.mount("/media", StaticFiles(directory=MEDIA_PATH), name="media")
app.include_router(generate_router)


@app.on_event("startup")
def startup_event():
    # Ленивая загрузка модели — только при первом запросе
    print("✅ Сервис запущен. Модель llama будет загружена при первом запросе.")
    # Не вызываем get_llm() здесь, чтобы сервис не падал


@app.get("/health", response_model=HealthResponse)
def health_check():
    return HealthResponse(status="ok")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
