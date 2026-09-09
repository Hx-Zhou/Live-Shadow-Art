# LongCat-Image 昇腾 API 使用说明

本 API 运行在华为云 ModelArts 远端服务器，不包含模型权重或 SSH 私钥。默认只监听
`127.0.0.1:8010`，组员必须先建立 SSH 隧道再调用，不能直接暴露到公网。

## 1. 服务器端启动

维护者登录服务器后执行：

```bash
cd /home/ma-user/work/longcat_deploy
# 可选：将 api.env.example 复制为不入库的 api.env，设置团队令牌和运行引擎。
# start_api.sh 会自动读取这个服务器本地文件。
bash ./start_api.sh
```

模型加载约需 1–2 分钟。以下命令返回 `ready: true` 后才可提交任务：

```bash
curl http://127.0.0.1:8010/health
```

停止服务：

```bash
bash /home/ma-user/work/longcat_deploy/stop_api.sh
```

API 与 NPU worker 日志位于 `/home/ma-user/work/longcat_deploy/api_state/logs/`，生成结果位于
`/home/ma-user/work/longcat_deploy/api_state/outputs/`。SQLite 任务库会保留状态；worker 异常重启时，
此前处于 `running` 的任务会重新排队。

## 2. 组员通过 SSH 隧道访问

在组员自己的电脑上保持以下命令运行：

```bash
ssh -o StrictHostKeyChecking=no -i KeyPair-2133.pem \
  -L 8010:127.0.0.1:8010 \
  ma-user@dev-modelarts.cn-southwest-2.huaweicloud.com -p 32584
```

此后 API 地址就是 `http://127.0.0.1:8010`。私钥只能由项目成员通过安全渠道获取，不能上传
到 GitHub、聊天记录或前端代码。若维护者配置了 `LONGCAT_API_TOKEN`，以下请求中的
`$LONGCAT_API_TOKEN` 需替换为团队内部共享的真实令牌。

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
  的负面提示词。`metadata` 会完整返回实际使用的正、负提示词。
- 如需逐字使用调用方提示词，设置 `applyStyleTemplate=false`，并显式传入 `negativePrompt`。

## 6. 运行状态边界

- `omni` 引擎及其 BF16/TP=2 配置已在 30/30 正式批次上验证；API 封装也已完成
  `HTTP → SQLite 队列 → NPU worker → 图片/元数据下载` 的 512×512、2 steps 端到端冒烟，
  下载文件与元数据 SHA-256 一致。
- `diffusers-lora` 引擎已用最终适配器完成真实 API 验证：单卡 Ascend 910B3、BF16、
  adapter scale `0.8`、1024×1024、50 steps、guidance `4.0`。关闭不必要的 VAE
  slicing/tiling 后，模型冷启动 `29.67 s`，新进程首图（含图编译/预热）`47.79 s`，
  常驻服务第二张稳态生成 `26.45 s`。
- `diffusers-lora` 还需要在服务器私有的 `api.env` 中设置最终适配器目录、强度、单卡设备，
  以及 `LONGCAT_API_EXTRA_PYTHONPATH=/home/ma-user/work/longcat_lora/eval_python:/home/ma-user/work/longcat_lora/src/LongCat-Image`。
- 已验证的 LoRA 1024 配置将 `LONGCAT_API_VAE_SLICING` 和 `LONGCAT_API_VAE_TILING`
  都设为 `0`；只有更高分辨率或显存不足时才按单项实验重新启用。
- 人物模板强化了“90°纯侧身、仅一只眼可见、禁止正面/三分之四视角”。生成模型仍可能
  偶发重复道具，课程演示应使用验收过的 seed，或对失败结果重试，不能假定每次完全遵循。
- vLLM-Omni 当前仅承担基础模型推理，不参与 LoRA 训练，也不宣称支持动态挂载本项目 LoRA。
