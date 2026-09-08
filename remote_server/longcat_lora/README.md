# LongCat-Image LoRA：Ascend 远端训练代码

该目录记录华为云远端服务器 `/home/ma-user/work/longcat_lora` 的训练代码。运行必须通过项目 SSH 入口访问；这里不提交模型权重、训练图片、checkpoint、缓存或密钥。

- 官方训练代码基线：`meituan-longcat/LongCat-Image` commit `f0e4c43c5ef74b011ff71570fbfc2bdffbc9ab06`。
- `upstream_reference/`：官方 LoRA 入口原样留档，用于审计。
- `train_npu/`：Ascend 910B3 适配入口和分阶段配置。
- `patches/`：只作用于隔离训练依赖的最小兼容补丁，不修改现有推理环境。
- 训练根目录：`/home/ma-user/work/longcat_lora`，与现有 `/home/ma-user/work/longcat_deploy` 推理基线隔离。

关键适配包括：移除 `.cuda()`、CUDA Flash-SDPA、TF32、bitsandbytes 和 NCCL 假设；使用 Accelerate + HCCL 双卡数据并行；BF16；LoRA rank 16；梯度检查点；有限 loss/grad 检查；原子 checkpoint 和恢复；NPU HBM 日志；修复官方入口在梯度累积时提前清零的问题。

`diffusers_0.35.2_npu_deprecation.patch` 删除 Diffusers 0.35.2 中已经超过移除版本、会在 NPU 构造 Flux block 时主动抛错的弃用检查，保留该版本原本选择的 `FluxAttnProcessor2_0_NPU`。这是隔离训练副本补丁。

阶段顺序固定为：512/20 步冒烟 → 768/200 步可行性 → 1024/800 步 MVP。每个阶段的结果达到门槛才进入下一阶段。
