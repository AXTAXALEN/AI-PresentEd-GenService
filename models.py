from pydantic import BaseModel, Field, field_validator
from typing import List, Optional


class SlideStructure(BaseModel):
    number: int
    title: str


class StructureRequest(BaseModel):
    topic: str
    profile: str = "default"
    # Количество слайдов в структуре презентации.
    # По умолчанию 7 (для базового тарифа), максимум 15 (для pro-тарифа).
    # Проверка прав доступа (basic / pro) выполняется на стороне общего
    # сервиса AI-PresentEd (Влад); микросервис только гарантирует, что
    # значение попадает в допустимый диапазон 1..15. Любое значение вне
    # диапазона будет отклонено Pydantic'ом со статусом 422 ДО выхода
    # из роутера.
    slides_count: int = Field(default=7, ge=1, le=15)


class StructureResponse(BaseModel):
    title: str
    slides: List[SlideStructure]


class SlidesRequest(BaseModel):
    topic: str
    profile: str = "default"
    structure: List[SlideStructure]


class SlideContent(BaseModel):
    number: int
    title: str
    content: str
    image_url: str
    image_alt: str
    image_prompt: str = ""

    @field_validator("image_alt", mode="before")
    @classmethod
    def image_alt_must_not_be_empty(cls, v, info):
        """
        Если image_alt пустой или слишком короткий — генерируем
        детерминированный fallback прямо в модели, чтобы фронтенд
        никогда не получил пустую строку.
        """
        if not v or (isinstance(v, str) and len(v.strip()) < 10):
            # info.data содержит уже провалидированные поля
            title = info.data.get("title", "")
            topic_hint = ""
            if title:
                return f"Фотография, иллюстрирующая тему «{title}»."
            return "Иллюстрация к слайду презентации."
        return v


class SlidesResponse(BaseModel):
    slides: List[SlideContent]


class HealthResponse(BaseModel):
    status: str
