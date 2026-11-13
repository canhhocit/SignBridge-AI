package com.signbridge.backend.ai;

import com.signbridge.backend.common.ContextType;

import java.util.List;

/**
 * Input cho SIGN_RECOGNIZE.
 *
 * @param frames         JPEG theo đúng thứ tự thời gian
 * @param allowedGlosses danh sách ký hiệu đưa vào prompt (mục 7.2)
 */
public record SignAiInput(
        ContextType context,
        List<byte[]> frames,
        List<String> allowedGlosses,
        List<String> personalChips,
        String previousIncoming) {
}
