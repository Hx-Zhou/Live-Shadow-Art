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

最新模型用 P01/P02/P05/P06 的 3268 帧训练，P03 的 736 帧验证；P04 曾做早期测试，本轮未评测。P03 门槛 0.70 时六类 Macro-F1 为 0.6972、正确率 76.63%、None 逐帧误判 1/245（0.41%）；门槛 0.75 时分别为 0.6630、75.00%、0/245。握拳和单指仍有明显漏识别，未完成验收。P03 多次用于模型选择，不能视为独立测试。

默认仍为规则基线。前端“加载 MLP 模型”选择 `modules/gesture-b/models/gesture/experimental/p06-2026-09-09/model.json` 即可试用最新模型；默认门槛为 0.75，加载文件不会改为 0.70。保持本地服务运行，否则 Worker 无法加载。

P05/P06 实验脚本和汇总指标见 `models/gesture/experimental/`，本轮附带约 390 KB 的 P06 自定义 MLP 权重。逐帧 JSONL、prepared 和 parity 数据未上传。详见 [工作报告](工作报告.md) 及实验目录 README。

## 成员 C 联调顺序

1. 独立启动，验证张掌激活、移动、握拳暂停、丢手后重新激活。
2. 按上表实现 GestureSource 适配，使用 `packages/schemas/` 校验输出。
3. 接正式输入路由/动作状态机，再联调攻击、跳跃、左右转身。
4. 在正式浏览器、设备和舞台测帧率、端到端延迟及自然操作误触，记录模型与配置版本。
