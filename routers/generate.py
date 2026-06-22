from fastapi import APIRouter, HTTPException, Header
from typing import Optional

from models import (
    StructureRequest, StructureResponse,
    SlidesRequest, SlidesResponse
)
from services.ai import generate_structure_ai, generate_slides_ai
from config import SERVICE_TOKEN

router = APIRouter(prefix="/generate", tags=["generate"])


def verify_token(x_service_token: Optional[str] = Header(None)):
    if x_service_token != SERVICE_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid or missing token")


@router.post("/structure", response_model=StructureResponse)
def generate_structure(request: StructureRequest, x_service_token: Optional[str] = Header(None)):
    verify_token(x_service_token)

    try:
        result = generate_structure_ai(
            topic=request.topic,
            profile=request.profile,
            slides_count=request.slides_count,
        )
        return StructureResponse(**result)
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"❌ ОШИБКА ГЕНЕРАЦИИ СТРУКТУРЫ:\n{error_trace}")
        raise HTTPException(status_code=500, detail=f"Structure generation failed: {e}")


@router.post("/slides", response_model=SlidesResponse)
def generate_slides(request: SlidesRequest, x_service_token: Optional[str] = Header(None)):
    verify_token(x_service_token)

    try:
        slides = generate_slides_ai(
            topic=request.topic,
            profile=request.profile,
            structure=request.structure
        )
        return SlidesResponse(slides=slides)
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"❌ ОШИБКА ГЕНЕРАЦИИ СЛАЙДОВ:\n{error_trace}")
        raise HTTPException(status_code=500, detail=f"Slides generation failed: {e}")
