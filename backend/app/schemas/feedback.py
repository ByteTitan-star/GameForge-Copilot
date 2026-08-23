"""用户反馈端点（向管理员发送反馈邮件）的请求/响应 schema。"""

from pydantic import BaseModel, Field


class FeedbackReq(BaseModel):
    """用户在 forge 失败时通过「联系管理员」提交的反馈。

    message 可空（纯错误上报）；error_summary 为前端运行时错误摘要，仅作邮件上下文。
    """

    run_id: str = Field(min_length=1, max_length=64)
    message: str = Field(default="", max_length=2000)
    error_summary: str = Field(default="", max_length=2000)


class FeedbackResp(BaseModel):
    """FeedbackResp API 响应体。

    场景：对应端点成功响应 data 字段。"""

    submitted: bool = True
