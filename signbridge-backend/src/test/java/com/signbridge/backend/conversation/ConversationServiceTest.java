package com.signbridge.backend.conversation;

import com.signbridge.backend.ai.ExpandAiOutput;
import com.signbridge.backend.ai.Highlight;
import com.signbridge.backend.ai.IconCode;
import com.signbridge.backend.ai.MockAiGateway;
import com.signbridge.backend.ai.SignAiInput;
import com.signbridge.backend.ai.SignAiOutput;
import com.signbridge.backend.ai.SummarizeAiInput;
import com.signbridge.backend.ai.SummarizeAiOutput;
import com.signbridge.backend.common.ApiException;
import com.signbridge.backend.common.ContextType;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/** Kiểm tra bước "không tin hoàn toàn vào AI" (mục 4.6, 7.4). */
class ConversationServiceTest {

    /** AI giả trả output tuỳ ý để thử các trường hợp xấu. */
    private static ConversationService serviceReturning(SignAiOutput sign, SummarizeAiOutput summary) {
        return new ConversationService(new MockAiGateway() {
            @Override
            public SignAiOutput recognizeSign(SignAiInput input) {
                return sign;
            }

            @Override
            public SummarizeAiOutput summarize(SummarizeAiInput input) {
                return summary;
            }
        }, 0.7);
    }

    private static SignAiOutput recognize(SignAiOutput aiOut, ContextType ctx) {
        return serviceReturning(aiOut, null).recognizeSign(ctx, List.of(), List.of(), null);
    }

    @Test
    void glossOutsideVocabularyBecomesUnknownAndSentenceIsCleared() {
        SignAiOutput out = recognize(new SignAiOutput(List.of("NHỨC ĐẦU", "THUỐC"), 0.95,
                "Mình bị nhức đầu.", List.of("a", "b", "c")), ContextType.PHARMACY);

        assertThat(out.glosses()).containsExactly("UNKNOWN", "THUỐC");
        assertThat(out.spokenSentence()).isEmpty();
        assertThat(out.confidence()).isLessThan(0.7);
    }

    @Test
    void glossIsNormalized() {
        SignAiOutput out = recognize(new SignAiOutput(List.of("  cà   phê ", "mang đi"), 0.9,
                "Cho mình cà phê mang đi.", List.of("a", "b", "c")), ContextType.CAFE);

        assertThat(out.glosses()).containsExactly("CÀ PHÊ", "MANG ĐI");
        assertThat(out.spokenSentence()).isEqualTo("Cho mình cà phê mang đi.");
    }

    @Test
    void glossFromOtherContextIsRejected() {
        SignAiOutput out = recognize(new SignAiOutput(List.of("CÀ PHÊ"), 0.9, "Cà phê.", List.of("a", "b", "c")),
                ContextType.PHARMACY);

        assertThat(out.glosses()).containsExactly("UNKNOWN");
    }

    @Test
    void lowConfidenceClearsSentence() {
        SignAiOutput out = recognize(new SignAiOutput(List.of("CÓ"), 0.5, "Có ạ.", List.of("a", "b", "c")),
                ContextType.CUSTOM);

        assertThat(out.spokenSentence()).isEmpty();
    }

    @Test
    void emptyGlossesIsNoSignDetected() {
        assertThatThrownBy(() -> recognize(new SignAiOutput(List.of(), 0.9, "", List.of("a", "b", "c")),
                ContextType.CUSTOM))
                .isInstanceOfSatisfying(ApiException.class, e -> assertThat(e.code()).isEqualTo("NO_SIGN_DETECTED"));
    }

    @Test
    void highlightNotInSummaryIsDropped() {
        SummarizeAiOutput ai = new SummarizeAiOutput("Quầy 3 • 15 phút",
                List.of(new Highlight(Highlight.HighlightType.COUNTER, "Quầy 3"),
                        new Highlight(Highlight.HighlightType.PRICE, "50.000đ")),
                IconCode.COUNTER, List.of("Cảm ơn", "Ở đâu?", "Đợi được"));

        SummarizeResponse out = serviceReturning(null, ai).summarize(ContextType.PUBLIC, new byte[]{1}, null);

        assertThat(out.highlights()).extracting(Highlight::text).containsExactly("Quầy 3");
    }

    @Test
    void wrongQuickReplyCountIsUpstreamError() {
        SummarizeAiOutput ai = new SummarizeAiOutput("Xong", List.of(), IconCode.CHECK, List.of("Cảm ơn"));

        assertThatThrownBy(() -> serviceReturning(null, ai).summarize(ContextType.CAFE, new byte[]{1}, null))
                .isInstanceOfSatisfying(ApiException.class, e -> assertThat(e.code()).isEqualTo("AI_UPSTREAM_ERROR"));
    }

    @Test
    void expandPassesThrough() {
        ExpandAiOutput out = new ConversationService(new MockAiGateway(), 0.7)
                .expand(ContextType.CAFE, List.of("Cà phê"), null);
        assertThat(out.spokenSentence()).contains("cà phê");
    }
}
