# LongCat-Image 昇腾 API 使用说明

本 API 运行在华为云 ModelArts 远端服务器，不包含模型权重或 SSH 私钥。默认只监听
`127.0.0.1:8010`，组员必须先建立 SSH 隧道再调用，不能直接暴露到公网。

## 1. 关机与恢复边界

模型、最终 LoRA、Python 环境、API 代码、任务库和结果均位于持久盘
`/home/ma-user/work`。服务器关机期间不能调用，且本仓库无权替代用户在华为云控制台开机。
当前 ModelArts 实例没有配置 `container_post_start` 钩子，user systemd 不可用、user cron
被禁用，因此不声称“操作系统启动时自动运行”。采用的是更符合按需计费场景的“首次使用时自动恢复”。

服务器开机后，维护者可执行：

```bash
bash /home/ma-user/work/longcat_deploy/ensure_api.sh
```

该命令会验证模型与 LoRA 目录、识别并清理关机残留的陈旧 PID、按当前 ModelArts 注入的 NPU
可见设备启动服务，并等待以下条件同时成立：`ready=true`、`engine=diffusers-lora`、
`adapterRevision=01add392…b6898c`。重复执行是安全的。

模型通常约 30 秒加载完成。以下命令返回 `ready: true` 后才可提交任务：

```bash
curl http://127.0.0.1:8010/health
```

停止服务：

```bash
bash /home/ma-user/work/longcat_deploy/stop_api.sh
```

最终 LoRA 的 API 与 NPU worker 日志位于
`/home/ma-user/work/longcat_deploy/api_state_lora/logs/`，生成结果位于
`/home/ma-user/work/longcat_deploy/api_state_lora/outputs/`。SQLite 任务库会保留状态；worker 异常重启时，
此前处于 `running` 的任务会重新排队。

## 2. 组员通过 SSH 隧道访问

推荐在仓库根目录运行一键恢复与隧道脚本：

```bash
./scripts/connect-longcat-api.sh /绝对路径/KeyPair-2133.pem
```

它会先远程执行 `ensure_api.sh`，只有最终 LoRA 就绪后才建立隧道。保持该终端运行。等价的手工隧道命令为：

```bash
ssh -o StrictHostKeyChecking=no -i KeyPair-2133.pem \
  -o UserKnownHostsFile=/dev/null \
  -L 8010:127.0.0.1:8010 \
  ma-user@dev-modelarts.cn-southwest-2.huaweicloud.com -p 32584
```

此后 API 地址就是 `http://127.0.0.1:8010`。私钥只能由项目成员通过安全渠道获取，不能上传
到 GitHub 或前端代码。若维护者配置了 `LONGCAT_API_TOKEN`，以下请求中的
`$LONGCAT_API_TOKEN` 需替换为团队内部共享的真实令牌。

ModelArts 实例重建后主机密钥可能变化；`UserKnownHostsFile=/dev/null` 避免旧记录导致 OpenSSH
禁用端口转发，但也意味着该连接不保存并校验主机指纹。若课程环境固定了可信指纹，应通过
`LONGCAT_SSH_KNOWN_HOSTS_FILE` 指向团队维护的专用 known-hosts 文件，替代 `/dev/null`。

## 3. 提交生成任务

人物提示词示例（服务器会将皮影风格模板追加到这段内容，并把最终提示词记入元数据）：

```bash
curl -X POST http://127.0.0.1:8010/api/v1/generations \
  -H "Authorization: Bearer $LONGCAT_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "kind": "character",
    "prompt": "哪吒少年武将，双丸子头，手持火尖枪，严格侧身全身，双臂与双腿轮廓分离",
    "width": 1024,
    "height": 1024,
    "steps": 50,
    "guidanceScale": 4.0,
    "seed": 42,
    "applyStyleTemplate": true
  }'
```

场景提示词示例：

```bash
curl -X POST http://127.0.0.1:8010/api/v1/generations \
  -H "Authorization: Bearer $LONGCAT_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "kind": "background",
    "prompt": "江南水乡，远景房屋、中层拱桥、近景芦苇，中央水面留出角色表演区",
    "width": 1024,
    "height": 576,
    "steps": 50,
    "guidanceScale": 4.0,
    "seed": 3407,
    "applyStyleTemplate": true
  }'
```

成功提交会返回：

```json
{
  "taskId": "任务编号",
  "status": "queued",
  "statusUrl": "/api/v1/tasks/任务编号"
}
```

## 4. 查询状态与下载图片

```bash
curl -H "Authorization: Bearer $LONGCAT_API_TOKEN" \
  http://127.0.0.1:8010/api/v1/tasks/任务编号

curl -H "Authorization: Bearer $LONGCAT_API_TOKEN" \
  -o result.png \
  http://127.0.0.1:8010/api/v1/tasks/任务编号/image

curl -H "Authorization: Bearer $LONGCAT_API_TOKEN" \
  http://127.0.0.1:8010/api/v1/tasks/任务编号/metadata
```

状态依次为 `queued`、`running`、`succeeded` 或 `failed`。由于当前 TP=2 会独占两张 NPU，
worker 有意串行执行任务；队列最多保留 8 个未完成任务，满载时返回 HTTP 429。

## 5. 参数边界与提示词

- 宽高必须是 16 的倍数，单图像素数不能超过 `1024 × 1024`。
- 默认人物尺寸为 `1024 × 1024`，场景为 `1024 × 576`。
- 已验证默认值为 BF16、50 steps、guidance 4.0、TP=2。
- `applyStyleTemplate=true` 时，服务器会追加 `piying_china_style`、皮革镂刻、平面色彩、
  侧身全身/中央留白等约束，并使用包含“写实人物、舞台摄影、现代服饰、普通插画、伪文字”
  的负面提示词。调用方提供的 `negativePrompt` 会与服务器模板合并，不会覆盖模板。
  `metadata` 会完整返回实际使用的正、负提示词。
- 如需逐字使用调用方提示词，设置 `applyStyleTemplate=false`，并显式传入 `negativePrompt`。

## 6. 运行状态边界

- `omni` 引擎及其 BF16/TP=2 配置已在 30/30 正式批次上验证；API 封装也已完成
  `HTTP → SQLite 队列 → NPU worker → 图片/元数据下载` 的 512×512、2 steps 端到端冒烟，
  下载文件与元数据 SHA-256 一致。
- `diffusers-lora` 引擎已用最终适配器完成真实 API 验证：单卡 Ascend 910B3、BF16、
  adapter scale `0.8`、1024×1024、50 steps、guidance `4.0`。关闭不必要的 VAE
  slicing/tiling 后，模型冷启动 `29.67 s`，新进程首图（含图编译/预热）`47.79 s`，
  常驻服务第二张稳态生成 `26.45 s`。
- 服务器私有 `api.env` 已固定最终适配器目录、哈希、强度、单卡设备，以及隔离的
  Diffusers/PEFT Python 路径；该文件不进入 Git。
- `health` 同时公开 `adapterRevision` 和 `adapterScale` 供项目后端校验。应用侧会拒绝基础
  `omni` 引擎、缺失版本号或非最终哈希，避免服务器重启后静默退回旧模型。
- 已验证的 LoRA 1024 配置将 `LONGCAT_API_VAE_SLICING` 和 `LONGCAT_API_VAE_TILING`
  都设为 `0`；只有更高分辨率或显存不足时才按单项实验重新启用。
- 人物模板强化了“90°纯侧身、仅一只眼可见、禁止正面/三分之四视角”。生成模型仍可能
  偶发重复道具，课程演示应使用验收过的 seed，或对失败结果重试，不能假定每次完全遵循。
- 背景模板已改为“景物限制在左右和下边缘、中央连续宣纸留白”，同 seed 实测消除了完整
  摄影式戏台和巨大中央占位轮廓，但仍出现过边缘小人物，因此背景结果必须审核后再进入演示缓存。
- vLLM-Omni 当前仅承担基础模型推理，不参与 LoRA 训练，也不宣称支持动态挂载本项目 LoRA。
