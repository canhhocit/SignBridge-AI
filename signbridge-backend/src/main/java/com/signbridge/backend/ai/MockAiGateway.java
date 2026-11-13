package com.signbridge.backend.ai;

import com.signbridge.backend.common.ContextType;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;

import java.util.List;

/**
 * Trả dữ liệu mẫu cố định (mục 4.2–4.4) để mobile làm việc khi chưa có AI thật.
 * <p>
 * Muốn thử luồng confidence thấp: gửi {@code personalChips=["MOCK_LOW"]}.
 */
@Component
@ConditionalOnProperty(name = "ai.mode", havingValue = "mock", matchIfMissing = true)
public class MockAiGateway implements AiGateway {

    static final String LOW_CONFIDENCE_TRIGGER = "MOCK_LOW";

    @Override
    public SignAiOutput recognizeSign(SignAiInput input) {
        if (input.personalChips().contains(LOW_CONFIDENCE_TRIGGER)) {
            return new SignAiOutput(List.of("UNKNOWN", "NGÀY"), 0.41, "",
                    List.of("Một ngày", "Hai ngày", "Một tuần", "Lâu rồi"));
        }
        return switch (input.context()) {
            case PHARMACY -> new SignAiOutput(List.of("ĐAU", "ĐẦU", "MUA", "THUỐC"), 0.86,
                    "Chào bạn, mình bị đau đầu, muốn mua thuốc.",
                    List.of("Đau đầu", "Mua thuốc", "Không buồn ngủ"));
            case CAFE -> new SignAiOutput(List.of("CÀ PHÊ", "ĐÁ", "MANG ĐI"), 0.84,
                    "Cho mình một cà phê đá mang đi nhé, cảm ơn bạn.",
                    List.of("Cà phê", "Đá", "Mang đi"));
            case PUBLIC -> new SignAiOutput(List.of("GIẤY TỜ", "Ở ĐÂU"), 0.80,
                    "Chào anh chị, cho mình hỏi nộp giấy tờ ở đâu ạ?",
                    List.of("Giấy tờ", "Ở đâu", "Cảm ơn"));
            case CUSTOM -> new SignAiOutput(List.of("XIN CHÀO", "CẢM ƠN"), 0.90,
                    "Xin chào, cảm ơn bạn.",
                    List.of("Xin chào", "Cảm ơn", "Có"));
        };
    }

    @Override
    public ExpandAiOutput expand(ExpandAiInput input) {
        return new ExpandAiOutput("Chào bạn, mình muốn: " + String.join(", ", input.chips()).toLowerCase()
                + ". Cảm ơn bạn!");
    }

    @Override
    public String transcribe(byte[] m4a, ContextType context) {
        return "Dạ bạn dùng Panadol xanh nha, uống một viên sau ăn, ngày hai lần, hộp này giá ba mươi lăm nghìn.";
    }

    @Override
    public SummarizeAiOutput summarize(SummarizeAiInput input) {
        return new SummarizeAiOutput(
                "Panadol Xanh • 1 viên sau ăn • Ngày 2 lần • 35.000đ",
                List.of(new Highlight(Highlight.HighlightType.DOSAGE, "1 viên"),
                        new Highlight(Highlight.HighlightType.QUANTITY, "Ngày 2 lần"),
                        new Highlight(Highlight.HighlightType.PRICE, "35.000đ")),
                IconCode.PILL,
                List.of("Lấy 1 hộp", "Chuyển khoản QR", "Có loại rẻ hơn không?"));
    }
}
