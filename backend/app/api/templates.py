"""模板只读 API（B5）。"""

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.response import ApiResponse
from app.forge.templates.loader import list_templates

router = APIRouter(prefix="/templates", tags=["templates"])


class TemplateItem(BaseModel):
    template_id: str
    title: str
    description: str
    requirement_seed: str
    tags: list[str]


@router.get("", response_model=ApiResponse[list[TemplateItem]])
async def get_templates() -> ApiResponse[list[TemplateItem]]:
    return ApiResponse(data=[TemplateItem.model_validate(t) for t in list_templates()])
