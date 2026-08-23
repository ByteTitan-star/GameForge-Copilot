import uuid

from pydantic import BaseModel

from app.enums import LLMProvider


class LLMConfigCreate(BaseModel):
    """LLMConfigCreate 数据传输对象。

    场景：API 或内部序列化契约。"""

    provider: LLMProvider
    model: str
    apikey: str
    base_url: str | None = None  # openai_compat 必填；官方 provider 可选（代理/私有网关）
    is_default: bool = False


class LLMConfigTestReq(BaseModel):
    """保存前探测：provider + model + apikey + base_url（不落库）。"""

    provider: LLMProvider
    model: str
    apikey: str
    base_url: str | None = None


class LLMConfigPatch(BaseModel):
    """LLMConfigPatch 数据传输对象。

    场景：API 或内部序列化契约。"""

    model: str | None = None
    is_default: bool | None = None


class LLMConfigResp(BaseModel):
    """LLMConfigResp API 响应体。

    场景：对应端点成功响应 data 字段。"""

    config_id: uuid.UUID
    provider: LLMProvider
    model: str
    apikey_masked: str
    base_url: str | None = None
    is_default: bool


class LLMConfigCreateResp(LLMConfigResp):
    """LLMConfigCreateResp API 响应体。

    场景：对应端点成功响应 data 字段。"""

    tested_ok: bool


class LLMConfigTestResp(BaseModel):
    """LLMConfigTestResp API 响应体。

    场景：对应端点成功响应 data 字段。"""

    config_id: uuid.UUID
    tested_ok: bool
    error: str | None = None


class LLMConfigDryTestResp(BaseModel):
    """LLMConfigDryTestResp API 响应体。

    场景：对应端点成功响应 data 字段。"""

    tested_ok: bool
    error: str | None = None


class LLMConfigDeleteResp(BaseModel):
    """LLMConfigDeleteResp API 响应体。

    场景：对应端点成功响应 data 字段。"""

    config_id: uuid.UUID
    deleted: bool = True
