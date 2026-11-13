package com.signbridge.backend.common;

import org.springframework.http.HttpStatus;

/** Lỗi nghiệp vụ, được GlobalExceptionHandler chuyển thành ErrorResponse. */
public class ApiException extends RuntimeException {

    private final HttpStatus status;
    private final String code;

    public ApiException(HttpStatus status, String code, String message) {
        super(message);
        this.status = status;
        this.code = code;
    }

    public HttpStatus status() {
        return status;
    }

    public String code() {
        return code;
    }

    public static ApiException invalidRequest(String message) {
        return new ApiException(HttpStatus.BAD_REQUEST, "INVALID_REQUEST", message);
    }

    public static ApiException payloadTooLarge(String message) {
        return new ApiException(HttpStatus.PAYLOAD_TOO_LARGE, "PAYLOAD_TOO_LARGE", message);
    }

    public static ApiException unsupportedMediaType(String message) {
        return new ApiException(HttpStatus.UNSUPPORTED_MEDIA_TYPE, "UNSUPPORTED_MEDIA_TYPE", message);
    }

    public static ApiException noSignDetected() {
        return new ApiException(HttpStatus.UNPROCESSABLE_CONTENT, "NO_SIGN_DETECTED",
                "Không nhận ra ký hiệu nào, vui lòng chọn thẻ từ khóa.");
    }

    public static ApiException noSpeechDetected() {
        return new ApiException(HttpStatus.UNPROCESSABLE_CONTENT, "NO_SPEECH_DETECTED",
                "Không nghe rõ, nhờ nhân viên nói lại.");
    }

    public static ApiException aiUpstreamError(String message) {
        return new ApiException(HttpStatus.BAD_GATEWAY, "AI_UPSTREAM_ERROR", message);
    }

    public static ApiException aiTimeout() {
        return new ApiException(HttpStatus.GATEWAY_TIMEOUT, "AI_TIMEOUT",
                "Dịch vụ AI phản hồi quá chậm, vui lòng thử lại.");
    }
}
