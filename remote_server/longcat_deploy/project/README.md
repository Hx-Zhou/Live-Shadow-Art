# LongCat-Image 昇腾 NPU 部署准备包

本目录用于把本地准备成果直接迁移到租用的昇腾服务器。当前只包含配置、检查脚本、测试集和基准程序，**不包含模型权重、Python 环境或容器镜像**。

## 已冻结的主线

- 主模型：`meituan-longcat/LongCat-Image`
- 推理精度：BF16
- 初始推理参数：50 steps，`guidance_scale=4.0`
- vLLM：`0.23.0`
- vLLM-Ascend：`0.23.0`
- vLLM-Omni：`v0.23.0rc1`
- Python：`3.12`
- CANN：`9.1.0`
- PyTorch / torch_npu：`2.10.0 / 2.10.0.post4`
- Triton Ascend：`3.2.2`

以上 vLLM-Ascend 组合来自官方兼容矩阵；vLLM-Omni `v0.23.0rc1` 与 vLLM `0.23.0` 对齐，并在该标签的模型矩阵中列出 LongCat 的 Ascend NPU 支持。禁止把不同发布线的 CANN、torch_npu 和 vLLM 随意混装。

## 建议租用规格

首选：

- `2 × 昇腾 910B 64 GB`，同机且 HCCS/HCCL 正常；
- 192 GB 以上主机内存，推荐 256 GB；
- 200 GB 以上可用 NVMe；
- 16 vCPU 起步，推荐 32 vCPU；
- Ubuntu/openEuler 均可，优先选择提供匹配官方容器和完整驱动的实例；
- 首次租用 48–72 小时，便于完成跑通、测试和一次优化。

如果租用平台能提供单卡可用 HBM 不低于 80 GiB 的昇腾实例，可以先尝试单卡；但官方公开的 71.2 GiB 是普通 GPU 基线，不是 NPU 实测值，因此仍需为运行时差异留余量。详细依据见 [算力与租用建议.md](算力与租用建议.md)。

## 目录说明

```text
成员A_昇腾LongCat部署准备包/
├── README.md
├── VERSION_LOCK.env
├── 算力与租用建议.md
├── 服务器执行手册.md
├── config/
│   ├── project.env.example
│   └── negative_prompt.txt
├── prompts/
│   └── selection_cases.json
├── scripts/
│   ├── 00_preflight.sh
│   ├── 01_start_container.sh
│   ├── 02_install_vllm_omni.sh
│   ├── 03_download_longcat.sh
│   ├── 04_smoke_longcat.sh
│   └── 05_run_benchmark.sh
├── tools/
│   └── benchmark.py
├── tests/
│   └── mock_t2i.py
└── templates/
    └── 评分表.csv
```

## 到租用服务器后的顺序

1. 上传整个目录，不要先安装任何软件。
2. 运行 `bash scripts/00_preflight.sh`，保存环境报告。
3. 对照 `VERSION_LOCK.env` 检查租用镜像；优先使用官方 vLLM-Ascend 容器作为底座。
4. `01`、`02`、`03` 脚本默认只显示成本，必须显式添加 `--execute` 才执行容器拉取、安装或权重下载。
5. 先运行 `04_smoke_longcat.sh`：768×768、10 步，仅验证 NPU 正确性。
6. 再运行 `05_run_benchmark.sh`：10 条任务提示词 × 3 个种子，生成性能 CSV 和逐图日志。
7. 基线稳定后再开始 profiler、融合算子或 cache 优化，不要在首图前改模型代码。

`tests/mock_t2i.py` 只用于在本机验证批测流程和CSV记录，不会生成真实图片，也不能替代NPU推理。

## 成本闸门

- 容器：预计十几至数十 GiB，取决于租用平台是否预装。
- LongCat 完整模型组件：vLLM-Omni 文档记录约 27.3 GiB。
- 目标测试集：30 张图 × 50 步；若做优化前后对照，至少生成 60 张。
- 本目录中的脚本均不会在本机自动执行上述下载。

## 官方依据

- [vLLM-Ascend 版本兼容矩阵](https://docs.vllm.ai/projects/ascend/en/main/community/versioning_policy.html)
- [vLLM-Ascend 安装说明](https://docs.vllm.ai/projects/ascend/en/main/getting_started/installation.html)
- [vLLM-Omni 文生图示例与资源表](https://docs.vllm.ai/projects/vllm-omni/en/latest/user_guide/examples/offline_inference/text_to_image/)
- [vLLM-Omni v0.23.0rc1 模型矩阵](https://github.com/vllm-project/vllm-omni/blob/v0.23.0rc1/docs/models/supported_models.md)
- [LongCat-Image 官方仓库](https://github.com/meituan-longcat/LongCat-Image)
