# 上游版本锁

服务器上的源码版本及本地修改如下：

| 组件 | 上游仓库 | 固定提交 | 本地修改 |
|---|---|---|---|
| vLLM | `https://github.com/vllm-project/vllm.git` | `89a77b10846fd96273cce78d86d2556ea582d26e` | `patches/vllm-requirements.patch` |
| vLLM-Ascend | `https://github.com/vllm-project/vllm-ascend.git` | `e2175d9c7e62b437391dfee996b1375674ba7c18` | `patches/vllm-ascend-requirements.patch` |
| vLLM-Omni | `https://github.com/vllm-project/vllm-omni.git` | `3d9fa8d53f1e79cfcd28b83581e92e566880e429` | `patches/vllm-omni-longcat-layers.patch` |

补丁必须应用在表中对应提交上。特别是 LongCat 的 10 个双流块和 20 个单流块修复，属于当前模型成功加载的必要兼容修改。

