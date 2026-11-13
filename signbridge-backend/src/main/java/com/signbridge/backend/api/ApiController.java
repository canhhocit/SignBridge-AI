package com.signbridge.backend.api;

import com.signbridge.backend.ai.ExpandAiOutput;
import com.signbridge.backend.ai.SignAiOutput;
import com.signbridge.backend.common.ApiException;
import com.signbridge.backend.common.ContextType;
import com.signbridge.backend.conversation.ConversationService;
import com.signbridge.backend.conversation.SummarizeResponse;
import jakarta.validation.Valid;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;
import tools.jackson.core.JacksonException;
import tools.jackson.core.type.TypeReference;
import tools.jackson.databind.json.JsonMapper;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.util.List;
import java.util.Map;
import java.util.Set;

/** 4 endpoint theo mục 4 docs/luong-xu-ly-chinh.md. */
@RestController
@RequestMapping(path = "/api", produces = MediaType.APPLICATION_JSON_VALUE)
public class ApiController {

    private static final long MAX_FRAME_BYTES = 250 * 1024;
    private static final long MAX_AUDIO_BYTES = 2 * 1024 * 1024;
    private static final int MAX_TEXT = 300;
    private static final Set<String> AUDIO_TYPES = Set.of("audio/m4a", "audio/mp4", "audio/x-m4a", "audio/aac");

    private final ConversationService service;
    private final JsonMapper json;

    public ApiController(ConversationService service, JsonMapper json) {
        this.service = service;
        this.json = json;
    }

    @GetMapping("/health")
    public Map<String, String> health() {
        return Map.of("status", "UP");
    }

    @PostMapping(path = "/sign", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public SignAiOutput sign(@RequestParam ContextType context,
                             @RequestParam List<MultipartFile> frames,
                             @RequestParam(required = false) String personalChips,
                             @RequestParam(required = false) String previousIncoming) {
        if (frames.size() < 4 || frames.size() > 16 || frames.size() % 4 != 0) {
            throw ApiException.invalidRequest("Số frame phải là 4, 8, 12 hoặc 16 (nhận " + frames.size() + ").");
        }
        for (MultipartFile f : frames) {
            if (!MediaType.IMAGE_JPEG_VALUE.equals(f.getContentType())) {
                throw ApiException.unsupportedMediaType("Frame phải là image/jpeg (nhận " + f.getContentType() + ").");
            }
            if (f.getSize() > MAX_FRAME_BYTES) {
                throw ApiException.payloadTooLarge("Mỗi frame phải ≤ 250 KB.");
            }
        }
        checkLength("previousIncoming", previousIncoming);
        List<String> chips = parseChips(personalChips);
        List<byte[]> bytes = frames.stream().map(ApiController::readBytes).toList();
        return service.recognizeSign(context, bytes, chips, blankToNull(previousIncoming));
    }

    @PostMapping(path = "/expand", consumes = MediaType.APPLICATION_JSON_VALUE)
    public ExpandAiOutput expand(@Valid @RequestBody ExpandRequest req) {
        return service.expand(req.context(), req.chips(), blankToNull(req.previousIncoming()));
    }

    @PostMapping(path = "/summarize", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public SummarizeResponse summarize(@RequestParam ContextType context,
                                       @RequestParam MultipartFile audio,
                                       @RequestParam(required = false) String previousOutgoing) {
        if (audio.getContentType() == null || !AUDIO_TYPES.contains(audio.getContentType())) {
            throw ApiException.unsupportedMediaType("Audio phải là m4a (nhận " + audio.getContentType() + ").");
        }
        if (audio.getSize() > MAX_AUDIO_BYTES) {
            throw ApiException.payloadTooLarge("Audio phải ≤ 2 MB.");
        }
        if (audio.isEmpty()) {
            throw ApiException.noSpeechDetected();
        }
        checkLength("previousOutgoing", previousOutgoing);
        return service.summarize(context, readBytes(audio), blankToNull(previousOutgoing));
    }

    private List<String> parseChips(String raw) {
        if (raw == null || raw.isBlank()) {
            return List.of();
        }
        List<String> chips;
        try {
            chips = json.readValue(raw, new TypeReference<List<String>>() { });
        } catch (JacksonException e) {
            throw ApiException.invalidRequest("personalChips phải là JSON array chuỗi.");
        }
        if (chips.size() > 20) {
            throw ApiException.invalidRequest("personalChips tối đa 20 phần tử.");
        }
        return chips;
    }

    private static void checkLength(String field, String value) {
        if (value != null && value.length() > MAX_TEXT) {
            throw ApiException.invalidRequest(field + " tối đa " + MAX_TEXT + " ký tự.");
        }
    }

    private static String blankToNull(String s) {
        return s == null || s.isBlank() ? null : s.trim();
    }

    private static byte[] readBytes(MultipartFile f) {
        try {
            return f.getBytes();
        } catch (IOException e) {
            throw new UncheckedIOException(e);
        }
    }
}
