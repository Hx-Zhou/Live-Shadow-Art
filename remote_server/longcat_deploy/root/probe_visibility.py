#!/usr/bin/env python3
"""Report which logical NPU IDs are usable under the current visibility env."""

import os
import traceback

import torch
import torch_npu  # noqa: F401


print(
    "env",
    {key: os.environ.get(key) for key in (
        "ASCEND_RT_VISIBLE_DEVICES",
        "ASCEND_VISIBLE_DEVICES",
        "NPU_VISIBLE_DEVICES",
    )},
)
try:
    print("available", torch.npu.is_available(), "count", torch.npu.device_count())
except Exception:
    traceback.print_exc(limit=2)

for index in (0, 1, 4, 7):
    try:
        value = torch.ones(1, dtype=torch.float32, device=f"npu:{index}")
        torch.npu.synchronize(index)
        print("device", index, "OK", value.cpu().item())
    except Exception as error:
        print("device", index, "ERROR", type(error).__name__, str(error).splitlines()[0])
