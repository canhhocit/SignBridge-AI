package com.signbridge.backend.ai;

import com.signbridge.backend.common.ContextType;

/**
 * Cổng gọi dịch vụ AI (mục 4.6). Chọn bản cài đặt bằng cấu hình {@code ai.mode=mock|real}.
 * <p>
 * Bản thật phải ném {@code ApiException.aiTimeout()} khi quá hạn và
 * {@code ApiException.aiUpstreamError(...)} khi AI lỗi hoặc trả JSON sai schema.
 */
public interface AiGateway {

    SignAiOutput recognizeSign(SignAiInput input);        // SIGN_RECOGNIZE

    ExpandAiOutput expand(ExpandAiInput input);           // EXPAND

    String transcribe(byte[] m4a, ContextType context);   // TRANSCRIBE

    SummarizeAiOutput summarize(SummarizeAiInput input);  // SUMMARIZE
}
