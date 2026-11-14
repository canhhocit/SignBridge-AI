import time
import os
import sys

# Tắt kiểm tra online của HuggingFace Hub
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

# Đảm bảo in tiếng Việt chuẩn trên Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from faster_whisper import WhisperModel

MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
MODEL_NAME = os.getenv("WHISPER_MODEL", "diepho/PhoWhisper-small-ct2")
DEFAULT_AUDIO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_audio-text", "test.mp3")

def test_transcription(audio_path, language="vi"):
    if not os.path.exists(audio_path):
        print(f"[-] File âm thanh không tồn tại: {audio_path}")
        print("[*] Hãy copy một file ghi âm (.m4a, .mp3, .wav) vào đường dẫn trên rồi thử lại.")
        return

    print(f"[*] Đang nạp model '{MODEL_NAME}' từ: {MODEL_DIR}...")
    t0 = time.time()
    cpu_threads = min(4, os.cpu_count() or 4)
    model = WhisperModel(
        MODEL_NAME,
        device="cpu",
        compute_type="int8",
        download_root=MODEL_DIR,
        local_files_only=True,
        cpu_threads=cpu_threads
    )
    t_load = time.time() - t0
    print(f"[+] Model đã sẵn sàng ({t_load:.2f}s)\n")

    print(f"[*] Đang nhận diện file: {os.path.basename(audio_path)} (ngôn ngữ: {language})...")
    t1 = time.time()
    segments, info = model.transcribe(
        audio_path,
        language=language,
        beam_size=1,                         # Greedy search tối ưu tốc độ
        temperature=0.0,
        condition_on_previous_text=False,
        vad_filter=True                      # Lọc khoảng lặng để tăng tốc
    )
    
    text_segments = []
    for s in segments:
        print(f"    [{s.start:.2f}s -> {s.end:.2f}s] {s.text}")
        text_segments.append(s.text)
    
    t_trans = time.time() - t1
    full_text = "".join(text_segments).strip()

    print("\n" + "=" * 50)
    print(" KẾT QUẢ ĐO KIỂM (BENCHMARK)")
    print("=" * 50)
    print(f"Văn bản nhận diện  : {full_text}")
    print(f"Độ dài file âm thanh: {info.duration:.2f} giây")
    print(f"Thời gian xử lý     : {t_trans:.2f} giây ({t_trans * 1000:.0f} ms)")
    if t_trans > 0:
        print(f"Tốc độ xử lý       : {info.duration / t_trans:.1f}x real-time")
    print(f"Đạt chuẩn < 5s     : {'ĐẠT' if t_trans < 5.0 else 'CHƯA ĐẠT'}")
    print("=" * 50)

if __name__ == "__main__":
    audio_file = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_AUDIO
    lang = sys.argv[2] if len(sys.argv) > 2 else "vi"
    test_transcription(audio_file, lang)
