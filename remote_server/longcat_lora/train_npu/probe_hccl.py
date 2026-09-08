#!/usr/bin/env python3
"""Two-rank HCCL smoke probe with no model state."""

import json
import os

import torch
import torch.distributed as dist
import torch_npu  # noqa: F401


rank = int(os.environ["RANK"])
local_rank = int(os.environ["LOCAL_RANK"])
torch.npu.set_device(local_rank)
dist.init_process_group(backend="hccl")
value = torch.tensor([rank + 1.0], device=f"npu:{local_rank}")
dist.all_reduce(value)
torch.npu.synchronize()
print(json.dumps({"rank": rank, "local_rank": local_rank, "sum": value.item(), "device": str(value.device)}), flush=True)
dist.destroy_process_group()
