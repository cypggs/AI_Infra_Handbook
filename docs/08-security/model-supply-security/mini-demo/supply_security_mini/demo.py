"""端到端 demo：五个供应链安全场景，全部确定性输出。

运行：python -m supply_security_mini.demo
"""

from __future__ import annotations

import numpy as np

from .mcp_integrity import (
    STATUS_DESCRIPTION_CHANGED,
    STATUS_HASH_MISMATCH,
    STATUS_OK,
    Client,
    Registry,
    make_email_tools,
)
from .pickle_scan import (
    build_safetensors,
    make_malicious_pickle,
    make_suspicious_pickle,
    parse_safetensors,
    pickle_dumps,
    scan_pickle,
)
from .poisoning import (
    accuracy,
    apply_backdoor,
    canary_trigger_rate,
    detect_poison,
    make_canaries,
    make_dataset,
    train_logreg,
    TRIGGER_RATE_THRESHOLD,
)
from .signing import build_manifest, sign_manifest, tamper, verify_bundle
from .watermark import (
    detect_watermark,
    embed_watermark,
    quantize,
    simulate_extraction,
    watermark_score,
)

_SIGNING_KEY = b"org-signing-key-2026"
_WM_KEY = b"owner-watermark-key"


def scenario_pickle() -> None:
    print("[S1] pickle opcode scanner vs safetensors")
    rng = np.random.default_rng(42)

    pure_data = pickle_dumps([float(rng.normal()) for _ in range(8)])
    numpy_arr = pickle_dumps(np.arange(12, dtype=np.float64).reshape(3, 4))
    malicious = make_malicious_pickle("id")

    for label, blob in [
        ("pure-data pickle", pure_data),
        ("numpy-array pickle", numpy_arr),
        ("RCE pickle (os.system)", malicious),
    ]:
        report = scan_pickle(blob)
        print(
            f"     {label:24s} rating={report.rating:11s} score={report.score:3d} "
            f"opcodes={report.n_opcodes:3d} imports={report.imports}"
        )

    st_blob = build_safetensors(
        {
            "layer.0.weight": {
                "dtype": "float32",
                "shape": [2, 3],
                "data": np.zeros((2, 3), dtype=np.float32),
            },
            "layer.0.bias": {
                "dtype": "float32",
                "shape": [3],
                "data": np.zeros(3, dtype=np.float32),
            },
        }
    )
    st = parse_safetensors(st_blob)
    print(
        f"     safetensors parse       ok={st.is_safetensors} tensors={st.n_tensors} "
        f"payload={st.total_bytes}B sha256={st.sha256[:16]}..."
    )


def scenario_signing() -> None:
    print("[S2] model artifact signing (merkle manifest + HMAC)")
    model_files = {
        "config.json": b'{"arch": "toy-transformer", "layers": 2}',
        "model.safetensors": np.arange(64, dtype=np.float32).tobytes(),
        "tokenizer.txt": b"the quick brown fox",
    }
    manifest = build_manifest(model_files)
    signature = sign_manifest(manifest, _SIGNING_KEY)
    print(f"     files={len(manifest.entries)} merkle_root={manifest.merkle_root[:16]}...")

    ok = verify_bundle(model_files, manifest, signature, _SIGNING_KEY)
    print(f"     intact bundle      verify_ok={ok.ok} bad_files={ok.bad_files}")

    tampered = tamper(model_files, "model.safetensors", b"\x00" * 256)
    bad = verify_bundle(tampered, manifest, signature, _SIGNING_KEY)
    print(f"     tampered weights   verify_ok={bad.ok} bad_files={bad.bad_files}")

    wrong_key = verify_bundle(model_files, manifest, signature, b"attacker-key")
    print(f"     wrong signing key  verify_ok={wrong_key.ok} signature_ok={wrong_key.signature_ok}")


def scenario_mcp() -> None:
    print("[S3] MCP tool manifest integrity")
    registry = Registry("toy-registry")
    client = Client()
    server = "email-server"

    v1_tools = make_email_tools(version=1, poisoned=False)
    v1_manifest = registry.publish(server, 1, v1_tools)

    # 正常加载 v1：全部通过
    ok = client.load(server, v1_tools, v1_manifest, registry)
    print(f"     load v1 (approved)    status={ok.status} loaded={len(client.loaded[server])}")

    # rug pull：服务器端代码被换成 v2，但 registry 仍记录 v1 的 hash
    rug_pull_tools = make_email_tools(version=2, poisoned=False)
    rug = client.load(server, rug_pull_tools, v1_manifest, registry)
    print(
        f"     rug pull (code swap)  status={rug.status} blocked={rug.blocked_tools}"
    )

    # tool poisoning：registry 发布 v2，描述里带隐藏指令；client 钉死 v1 描述
    v2_poisoned = make_email_tools(version=2, poisoned=True)
    registry.publish(server, 2, v2_poisoned)
    poison = client.load(server, v2_poisoned, v1_manifest, registry)
    old, new = poison.description_diffs["send_email"]
    print(f"     tool poisoning        status={poison.status}")
    print(f"       send_email description approved: {old[:44]}...")
    print(f"       send_email description served  : {new[:44]}...")


def scenario_poisoning() -> None:
    print("[S4] training-data poisoning detection (canary trigger rate)")
    data = make_dataset()
    canaries = make_canaries()

    clean_model = train_logreg(data)
    poisoned_data = apply_backdoor(data, poison_fraction=0.15)
    backdoored_model = train_logreg(poisoned_data)

    clean_acc = accuracy(clean_model, data)
    poisoned_acc = accuracy(backdoored_model, poisoned_data)
    clean_rate = canary_trigger_rate(clean_model, canaries)
    backdoor_rate = canary_trigger_rate(backdoored_model, canaries)

    print(
        f"     clean model      acc={clean_acc:.3f} canary_trigger_rate={clean_rate:.3f} "
        f"alarm={detect_poison(clean_rate)}"
    )
    print(
        f"     backdoored model acc={poisoned_acc:.3f} canary_trigger_rate={backdoor_rate:.3f} "
        f"alarm={detect_poison(backdoor_rate)} (threshold={TRIGGER_RATE_THRESHOLD})"
    )


def scenario_watermark() -> None:
    print("[S5] model weight watermark (deterministic PR pattern)")
    rng = np.random.default_rng(123)
    weights = rng.normal(0.0, 0.02, size=4096)
    strength = 0.05

    marked = embed_watermark(weights, _WM_KEY, strength)
    s_orig = watermark_score(weights, _WM_KEY)
    s_marked = watermark_score(marked, _WM_KEY)
    det_marked = detect_watermark(marked, _WM_KEY, strength)

    print(
        f"     unmarked score={s_orig:+.4f}  marked score={s_marked:+.4f} "
        f"threshold={det_marked.threshold:.4f} detected={det_marked.detected}"
    )

    for label, suspect in [
        ("quantized (2 decimals)", quantize(marked)),
        ("noisy (std=0.5)", simulate_extraction(marked, noise_std=0.5)),
        ("re-watermarked by thief", embed_watermark(marked, b"attacker-key", strength)),
        ("rounded to int (step >> strength)", quantize(marked, decimals=0)),
    ]:
        res = detect_watermark(suspect, _WM_KEY, strength)
        print(
            f"     {label:32s} score={res.score:+.4f} detected={res.detected}"
        )


def run_demo() -> None:
    scenario_pickle()
    scenario_signing()
    scenario_mcp()
    scenario_poisoning()
    scenario_watermark()


if __name__ == "__main__":
    run_demo()
