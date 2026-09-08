#!/usr/bin/env python3
"""Verify that both visible Ascend NPUs execute and synchronize real BF16 work."""

from __future__ import annotations

import json
import time

import torch
import torch_npu  # noqa: F401 - registers the NPU backend


def probe(index: int) -> dict[str, object]:
    device = torch.device(f"npu:{index}")
    torch.npu.set_device(device)
    torch.npu.synchronize(device)

    # This is deliberately large enough to exercise the compute path but small
    # enough to leave ample HBM for a non-destructive pre-deployment check.
    size = 4096
    generator = torch.Generator(device=device).manual_seed(20260907 + index)
    left = torch.randn((size, size), device=device, dtype=torch.bfloat16, generator=generator)
    right = torch.randn((size, size), device=device, dtype=torch.bfloat16, generator=generator)
    torch.npu.synchronize(device)
    started = time.perf_counter()
    product = left @ right
    checksum = float(product.float().mean().cpu())
    torch.npu.synchronize(device)
    elapsed = time.perf_counter() - started
    free_bytes, total_bytes = torch.npu.mem_get_info(index)
    return {
        "logical_index": index,
        "name": torch.npu.get_device_name(index),
        "dtype": str(product.dtype),
        "shape": list(product.shape),
        "elapsed_seconds": elapsed,
        "checksum": checksum,
        "hbm_free_bytes": free_bytes,
        "hbm_total_bytes": total_bytes,
        "status": "PASS",
    }


def main() -> None:
    count = torch.npu.device_count()
    if not torch.npu.is_available() or count != 2:
        raise RuntimeError(f"Expected exactly two visible NPUs, available={torch.npu.is_available()} count={count}")
    report = {
        "torch": torch.__version__,
        "torch_npu": torch_npu.__version__,
        "npu_available": torch.npu.is_available(),
        "npu_count": count,
        "devices": [probe(index) for index in range(count)],
        "overall": "PASS",
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
