"""Convert model VSL (Keras, 2.764 nhãn) → TFLite cho mobile + labels.json cho server (luồng Hybrid, mục 4.2a).

Chạy trong venv riêng (tools/requirements-vsl.txt), KHÔNG cài vào venv server:
    python tools/convert_vsl_tflite.py \
        --model  <repo VSL>/Models/checkpoints/final_model.keras \
        --labels <repo VSL>/Logs/label_map.json \
        --out-dir data/vsl --quant dynamic

Output trong --out-dir:
    vsl_model.tflite   model cho mobile, input [1, 60, 201] float32, output [1, N] softmax
    labels.json        list nhãn theo index (labels[i] ↔ output[i]); server đọc qua VSL_LABELS_PATH
    vsl_model.json     metadata: shape, lượng tử hoá, sha256, kết quả so khớp Keras ↔ TFLite
    vsl_golden.json    (--golden N) input mẫu + top-5 kỳ vọng để mobile test unit phần nạp TFLite

Không đọc/ghi dữ liệu người dùng; chỉ dùng input tổng hợp để so khớp.
"""
import argparse
import hashlib
import json
import os
import sys
import time

import numpy as np

SEQ_LEN = 60
N_POSE, N_HAND = 25, 21
N_FEATURES = (N_POSE + 2 * N_HAND) * 3   # 201 = (25 pose thân trên + 21 tay trái + 21 tay phải) × (x, y, z)
ACCEPT_THRESHOLD = 0.7                   # = VSL_MIN_GLOSS_CONFIDENCE mặc định của server


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_labels(path):
    """label_map.json của repo gốc là {"nhãn": index}; trả list theo index, kiểm tra index liền mạch."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    labels = [None] * len(data)
    for name, idx in data.items():
        if not isinstance(idx, int) or not 0 <= idx < len(data) or labels[idx] is not None:
            sys.exit(f"[-] label_map.json có index không hợp lệ/trùng: {name!r} → {idx!r}")
        labels[idx] = name
    return labels


def synthetic_inputs(n, seed):
    """Chuỗi landmark tổng hợp gần phân bố thật: x, y ∈ [0, 1], z nhỏ; ~30% frame mất 1 bàn tay (= 0)."""
    rng = np.random.default_rng(seed)
    x = np.empty((n, SEQ_LEN, N_FEATURES), np.float32)
    pts = x.reshape(n, SEQ_LEN, -1, 3)
    pts[..., :2] = rng.uniform(0.0, 1.0, pts[..., :2].shape)
    pts[..., 2] = rng.normal(0.0, 0.1, pts[..., 2].shape)
    # Làm mượt theo thời gian để giống chuyển động liên tục
    for t in range(1, SEQ_LEN):
        pts[:, t] = 0.8 * pts[:, t - 1] + 0.2 * pts[:, t]
    hand_missing = rng.random((n, SEQ_LEN, 2)) < 0.3
    for side in range(2):
        start = N_POSE + side * N_HAND
        pts[:, :, start:start + N_HAND][hand_missing[..., side]] = 0.0
    return x


def convert(model, quant, allow_flex):
    import tempfile

    import keras
    import tensorflow as tf

    # Keras 3: freeze thẳng tf.function lỗi do biến trạng thái (seed dropout trong LSTM)
    # → export SavedModel qua ExportArchive (batch cố định 1) rồi convert.
    saved_dir = tempfile.mkdtemp(prefix="vsl-savedmodel-")
    archive = keras.export.ExportArchive()
    archive.track(model)
    archive.add_endpoint(
        name="serve",
        fn=lambda landmarks: model(landmarks, training=False),
        input_signature=[tf.TensorSpec([1, SEQ_LEN, N_FEATURES], tf.float32, name="landmarks")],
    )
    archive.write_out(saved_dir)

    converter = tf.lite.TFLiteConverter.from_saved_model(saved_dir)
    if quant == "dynamic":
        converter.optimizations = [tf.lite.Optimize.DEFAULT]
    ops = [tf.lite.OpsSet.TFLITE_BUILTINS]
    if allow_flex:
        # Cần thêm tensorflow-lite-select-tf-ops ở mobile (APK nặng hơn) — chỉ dùng khi builtins không đủ
        ops.append(tf.lite.OpsSet.SELECT_TF_OPS)
    converter.target_spec.supported_ops = ops
    return converter.convert()


def run_tflite(tflite_path, inputs):
    import tensorflow as tf

    interp = tf.lite.Interpreter(model_path=tflite_path)
    interp.allocate_tensors()
    inp, out = interp.get_input_details()[0], interp.get_output_details()[0]
    results, times = [], []
    for x in inputs:
        interp.set_tensor(inp["index"], x[None])
        t0 = time.perf_counter()
        interp.invoke()
        times.append((time.perf_counter() - t0) * 1000)
        results.append(interp.get_tensor(out["index"])[0])
    return np.stack(results), times, inp, out


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--model", required=True, help="final_model.keras")
    p.add_argument("--labels", required=True, help="label_map.json ({nhãn: index}) hoặc list nhãn")
    p.add_argument("--out-dir", default="data/vsl")
    # float16 đã thử (2026-11-14): lệch Keras nhiều hơn int8 → không hỗ trợ
    p.add_argument("--quant", choices=("dynamic", "none"), default="dynamic",
                   help="dynamic: trọng số int8 (~5.5MB, mặc định); none: float32 (~21MB, khớp Keras tuyệt đối)")
    p.add_argument("--allow-flex", action="store_true", help="cho phép SELECT_TF_OPS nếu builtins không convert được")
    p.add_argument("--check", type=int, default=256, help="số input tổng hợp để so khớp Keras ↔ TFLite")
    p.add_argument("--golden", type=int, default=2, help="số mẫu ghi vào vsl_golden.json (0 = bỏ)")
    p.add_argument("--seed", type=int, default=7)
    args = p.parse_args()

    import keras

    labels = load_labels(args.labels)
    print(f"[*] Nạp model {args.model} …")
    model = keras.models.load_model(args.model, compile=False)
    in_shape, out_shape = tuple(model.input_shape), tuple(model.output_shape)
    if in_shape[1:] != (SEQ_LEN, N_FEATURES):
        sys.exit(f"[-] Input model {in_shape} ≠ (None, {SEQ_LEN}, {N_FEATURES}) — tiền xử lý đã đổi, cập nhật script.")
    if out_shape[-1] != len(labels):
        sys.exit(f"[-] Model có {out_shape[-1]} lớp nhưng labels có {len(labels)} nhãn.")

    os.makedirs(args.out_dir, exist_ok=True)
    tflite_path = os.path.join(args.out_dir, "vsl_model.tflite")
    print(f"[*] Convert TFLite (quant={args.quant}) …")
    with open(tflite_path, "wb") as f:
        f.write(convert(model, args.quant, args.allow_flex))

    with open(os.path.join(args.out_dir, "labels.json"), "w", encoding="utf-8") as f:
        json.dump(labels, f, ensure_ascii=False, indent=0)

    # So khớp Keras ↔ TFLite trên input tổng hợp (sanity check; độ chính xác thật cần video thật)
    xs = synthetic_inputs(max(args.check, args.golden), args.seed)
    ref = model.predict(xs, batch_size=32, verbose=0)
    got, times, inp, out = run_tflite(tflite_path, xs)
    top1 = float(np.mean(ref.argmax(1) == got.argmax(1)))
    ref_top5 = np.argsort(-ref, 1)[:, :5]
    top5_hit = float(np.mean([g in r for g, r in zip(got.argmax(1), ref_top5)]))
    max_diff = float(np.max(np.abs(ref - got)))
    # Điều server thật sự dùng: nhãn top-1 khi model tự tin (>= ngưỡng 0.7 của /api/sign/glosses)
    confident = ref.max(1) >= ACCEPT_THRESHOLD
    top1_confident = float(np.mean(ref.argmax(1)[confident] == got.argmax(1)[confident])) if confident.any() else None
    same_decision = float(np.mean((ref.argmax(1) == got.argmax(1)) & ((got.max(1) >= ACCEPT_THRESHOLD) == confident)))

    meta = {
        "source_model_sha256": sha256(args.model),
        "tflite_sha256": sha256(tflite_path),
        "tflite_bytes": os.path.getsize(tflite_path),
        "quantization": args.quant,
        "flex_ops": args.allow_flex,
        "input": {"name": inp["name"], "shape": [int(d) for d in inp["shape"]], "dtype": "float32"},
        "output": {"name": out["name"], "shape": [int(d) for d in out["shape"]], "activation": "softmax"},
        "num_labels": len(labels),
        "preprocessing": {
            "landmarks": "MediaPipe Holistic: pose[0..24], left_hand[0..20], right_hand[0..20]; (x, y, z) chuẩn hoá ảnh",
            "missing_part": "điền 0",
            "sequence": f"nội suy cubic theo thời gian về {SEQ_LEN} frame",
            "layout": "[frame][pose 25×3 | left 21×3 | right 21×3]",
        },
        "parity_vs_keras": {
            "samples": len(xs), "input": "synthetic",
            "top1_agreement": round(top1, 4), "tflite_top1_in_keras_top5": round(top5_hit, 4),
            "max_abs_prob_diff": round(max_diff, 6),
            "keras_confident_samples": int(confident.sum()),
            "top1_agreement_when_keras_confident": None if top1_confident is None else round(top1_confident, 4),
            "same_accept_decision": round(same_decision, 4),
        },
        "desktop_cpu_latency_ms": {"mean": round(float(np.mean(times)), 2), "p95": round(float(np.percentile(times, 95)), 2)},
    }
    with open(os.path.join(args.out_dir, "vsl_model.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    if args.golden:
        golden = [{
            "input": np.round(xs[i], 6).tolist(),
            "expected_top5": [{"index": int(j), "label": labels[j], "prob": round(float(got[i][j]), 6)}
                              for j in np.argsort(-got[i])[:5]],
        } for i in range(args.golden)]
        with open(os.path.join(args.out_dir, "vsl_golden.json"), "w", encoding="utf-8") as f:
            json.dump(golden, f, ensure_ascii=False)

    print(json.dumps({k: meta[k] for k in ("tflite_bytes", "quantization", "parity_vs_keras",
                                           "desktop_cpu_latency_ms")}, ensure_ascii=False, indent=2))
    print(f"[+] Xong: {args.out_dir}")


if __name__ == "__main__":
    main()
