"""Lỗi nghiệp vụ + handler chung: mọi lỗi trả {"error": {"code", "message"}} (mục 4.0)."""
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("SignBridge.API")


class ApiError(Exception):
    """Chỉ tạo qua các factory bên dưới để mã lỗi khớp bảng mục 4.0."""

    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message

    @staticmethod
    def invalid_request(message: str) -> "ApiError":
        return ApiError(400, "INVALID_REQUEST", message)

    @staticmethod
    def payload_too_large(message: str) -> "ApiError":
        return ApiError(413, "PAYLOAD_TOO_LARGE", message)

    @staticmethod
    def unsupported_media_type(message: str) -> "ApiError":
        return ApiError(415, "UNSUPPORTED_MEDIA_TYPE", message)

    @staticmethod
    def no_sign_detected() -> "ApiError":
        return ApiError(422, "NO_SIGN_DETECTED", "Không nhận ra ký hiệu nào, vui lòng chọn thẻ từ khóa.")

    @staticmethod
    def no_speech_detected() -> "ApiError":
        return ApiError(422, "NO_SPEECH_DETECTED", "Không nghe rõ, nhờ nhân viên nói lại.")

    @staticmethod
    def ai_upstream_error(message: str) -> "ApiError":
        return ApiError(502, "AI_UPSTREAM_ERROR", message)

    @staticmethod
    def ai_timeout() -> "ApiError":
        return ApiError(504, "AI_TIMEOUT", "Dịch vụ AI phản hồi quá chậm, vui lòng thử lại.")

    @staticmethod
    def database_unavailable() -> "ApiError":
        # Mở rộng của bản Python (API thẻ /api/chips), không có trong bảng mục 4.0
        return ApiError(503, "DATABASE_NOT_AVAILABLE", "Cơ sở dữ liệu chưa sẵn sàng.")


def error_body(code: str, message: str) -> dict:
    return {"error": {"code": code, "message": message}}


def _respond(request: Request, status: int, code: str, message: str) -> JSONResponse:
    # Middleware log đọc lại mã lỗi này (tương đương ERROR_CODE_ATTR bên Spring)
    request.state.error_code = code
    return JSONResponse(status_code=status, content=error_body(code, message))


_HTTP_CODES = {404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED"}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def handle_api(request: Request, e: ApiError):
        if e.status >= 500:
            logger.warning("%s %s", e.code, e.message)
        return _respond(request, e.status, e.code, e.message)

    @app.exception_handler(RequestValidationError)
    async def handle_validation(request: Request, e: RequestValidationError):
        # Không đưa giá trị input vào message (có thể là nội dung người dùng)
        parts = []
        for err in e.errors():
            loc = ".".join(str(x) for x in err.get("loc", ()) if x not in ("body", "query", "path"))
            parts.append(f"{loc}: {err.get('msg', '')}" if loc else err.get("msg", ""))
        return _respond(request, 400, "INVALID_REQUEST", "Request không hợp lệ: " + "; ".join(parts))

    @app.exception_handler(StarletteHTTPException)
    async def handle_http(request: Request, e: StarletteHTTPException):
        code = _HTTP_CODES.get(e.status_code, "INVALID_REQUEST" if e.status_code < 500 else "INTERNAL_ERROR")
        return _respond(request, e.status_code, code, str(e.detail))

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, e: Exception):
        logger.error("Lỗi không mong đợi: %s", type(e).__name__)
        return _respond(request, 500, "INTERNAL_ERROR", "Lỗi máy chủ.")
