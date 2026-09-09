# 成员 B：独立手势模块交付

代码位于 `modules/gesture-b/`。该模块可独立运行，包含摄像头、MediaPipe Worker、规则分类、数据采集、校准、MLP 训练、测试及实验汇总。尚未连接仓库 `web/` 正式舞台，也没有改动三方公共契约。

## 启动与验证

```sh
cd modules/gesture-b
npm run setup
npm start
```

需 Node.js 20+。打开 http://localhost:8765，点击启动摄像头。首次 setup 下载固定版本 MediaPipe；浏览器处理本地视频，不上传逐帧关键点。

```sh
npm test
python -m pip install -r requirements.txt
python tests/test_training.py
```

代码测试共 11 项 Node + 4 项 Python。实际舞台集成和设备性能仍需联调。

## 必须完成的协议适配

正式接口应依仓库要求在 `web/src/gesture/GestureSource.ts` 实现。本次只上传已完成的独立模块，该接口适配器尚未实现。以下差异不能忽略：

| 独立 SDK | 团队公共契约 | 对接要求 |
|---|---|---|
| `performance.now()` 毫秒 | Unix 毫秒时间戳 | 适配器建立时钟偏移；不能直接复用数值 |
| activate / pause | open_palm / fist | 显式映射 |
| swipe | swipe_left / swipe_right | 需输出手掌轨迹方向；食指 direction 不是挥动方向，不能用它猜测 |
| point / victory | 无对应枚举 | 保留为本地信号，或三方确认后扩展公共契约 |
| gesture_control，position 等字段 | ContinuousSignal，present/palm/direction/velocity/pinchStrength | 显式转换；按相邻样本时间计算 velocity，并确认暂停语义 |
| gesture_status lost | present=false | 丢手时发无手信号，清空速度并让舞台进入安全状态 |
| version、confidenceKind、position 等额外事件字段 | additionalProperties=false | 适配后只保留公共 Schema 允许的字段 |

SDK 源码：`modules/gesture-b/web/src/gesture/`。模块内部 `schemas/` 仅用于独立实验台，不替换 `packages/schemas/`。前端迁移还需适配 Worker/vendor 静态 URL，并在 React 卸载时释放摄像头。

## 实验状态

P01/P02 训练，P03 验证，P04 做过早期测试；后续门槛/L2 比较未使用 P04 调参。P03 门槛 0.70、L2=0 的六类 Macro-F1 为 0.4966，None 被逐帧识别为动作比例为 20%，尚未达标；该比例不是每分钟误触次数。

默认仍为规则基线。`models/gesture/experimental/` 包含候选配置和汇总指标，不包含权重或逐帧数据。真实 JSONL、prepared、parity、训练快照和模型权重通过团队单独约定的渠道共享。

## 成员 C 联调顺序

1. 独立启动，验证张掌激活、移动、握拳暂停、丢手后重新激活。
2. 按上表实现 GestureSource 适配，使用 `packages/schemas/` 校验输出。
3. 接正式输入路由/动作状态机，再联调攻击、跳跃、左右转身。
4. 在正式浏览器、设备和舞台测帧率、端到端延迟及自然操作误触，记录模型与配置版本。
