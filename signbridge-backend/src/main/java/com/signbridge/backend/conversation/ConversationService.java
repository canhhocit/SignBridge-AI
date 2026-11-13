package com.signbridge.backend.conversation;

import com.signbridge.backend.ai.AiGateway;
import com.signbridge.backend.ai.ExpandAiInput;
import com.signbridge.backend.ai.ExpandAiOutput;
import com.signbridge.backend.ai.Highlight;
import com.signbridge.backend.ai.SignAiInput;
import com.signbridge.backend.ai.SignAiOutput;
import com.signbridge.backend.ai.SummarizeAiInput;
import com.signbridge.backend.ai.SummarizeAiOutput;
import com.signbridge.backend.common.ApiException;
import com.signbridge.backend.common.ContextType;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.text.Normalizer;
import java.util.List;
import java.util.Locale;

/** Gọi AI và kiểm tra lại output trước khi trả cho mobile (mục 4.6, 7.4). Không lưu gì. */
@Service
public class ConversationService {

    private final AiGateway ai;
    private final double confidenceThreshold;

    public ConversationService(AiGateway ai,
                               @Value("${sign.confidence-threshold:0.7}") double confidenceThreshold) {
        this.ai = ai;
        this.confidenceThreshold = confidenceThreshold;
    }

    public SignAiOutput recognizeSign(ContextType context, List<byte[]> frames,
                                      List<String> personalChips, String previousIncoming) {
        List<String> allowed = SignVocabulary.allowedFor(context);
        SignAiOutput out = ai.recognizeSign(
                new SignAiInput(context, frames, allowed, personalChips, previousIncoming));
        if (out == null || out.glosses() == null || out.suggestedChips() == null) {
            throw ApiException.aiUpstreamError("AI trả thiếu trường bắt buộc.");
        }

        // Mục 7.4: ép glosses về bộ ký hiệu đã gửi
        List<String> glosses = out.glosses().stream()
                .map(ConversationService::normalizeGloss)
                .map(g -> allowed.contains(g) ? g : SignVocabulary.UNKNOWN)
                .toList();
        if (glosses.isEmpty()) {
            throw ApiException.noSignDetected();
        }

        boolean hasUnknown = glosses.contains(SignVocabulary.UNKNOWN);
        boolean needConfirm = hasUnknown || out.confidence() < confidenceThreshold;
        double confidence = hasUnknown ? Math.min(out.confidence(), confidenceThreshold - 0.01) : out.confidence();
        String sentence = needConfirm || out.spokenSentence() == null ? "" : out.spokenSentence();
        return new SignAiOutput(glosses, confidence, sentence, out.suggestedChips());
    }

    public ExpandAiOutput expand(ContextType context, List<String> chips, String previousIncoming) {
        ExpandAiOutput out = ai.expand(new ExpandAiInput(context, chips, previousIncoming));
        if (out == null || out.spokenSentence() == null || out.spokenSentence().isBlank()) {
            throw ApiException.aiUpstreamError("AI không trả câu nói.");
        }
        return out;
    }

    public SummarizeResponse summarize(ContextType context, byte[] audio, String previousOutgoing) {
        String transcript = ai.transcribe(audio, context);
        if (transcript == null || transcript.isBlank()) {
            throw ApiException.noSpeechDetected();
        }
        SummarizeAiOutput out = ai.summarize(new SummarizeAiInput(context, transcript.trim(), previousOutgoing));
        if (out == null || out.summary() == null || out.iconCode() == null
                || out.quickReplies() == null || out.quickReplies().size() != 3) {
            throw ApiException.aiUpstreamError("AI trả tóm tắt sai schema.");
        }

        // Mục 4.6 bước 3: bỏ highlight không xuất hiện nguyên văn trong summary
        List<Highlight> highlights = out.highlights() == null ? List.of() : out.highlights().stream()
                .filter(h -> h != null && h.type() != null && h.text() != null && !h.text().isBlank())
                .filter(h -> out.summary().contains(h.text()))
                .toList();
        return new SummarizeResponse(transcript.trim(), out.summary(), highlights, out.iconCode(), out.quickReplies());
    }

    static String normalizeGloss(String gloss) {
        if (gloss == null) {
            return SignVocabulary.UNKNOWN;
        }
        String g = Normalizer.normalize(gloss, Normalizer.Form.NFC).trim().replaceAll("\\s+", " ");
        return g.toUpperCase(Locale.ROOT);
    }
}
