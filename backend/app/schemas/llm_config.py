import uuid

from pydantic import BaseModel

from app.enums import LLMProvider


class LLMConfigCreate(BaseModel):
    provider: LLMProvider
    model: str
    apikey: str
    base_url: str | None = None  # openai_compat 必填
    is_default: bool = False


class LLMConfigPatch(BaseModel):
    model: str | None = None
    is_default: bool | None = None


class LLMConfigResp(BaseModel):
    config_id: uuid.UUID
    provider: LLMProvider
    model: str
    apikey_masked: str
    base_url: str | None = None
    is_default: bool


class LLMConfigCreateResp(LLMConfigResp):
    tested_ok: bool


class LLMConfigTestResp(BaseModel):
    config_id: uuid.UUID
    tested_ok: bool
    error: str | None = None


class LLMConfigDeleteResp(BaseModel):
    config_id: uuid.UUID
    deleted: bool = True
