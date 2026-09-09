# 光影新生 · 成员 B 手势识别模块

本交付依据《光影新生_AI实时互动皮影戏台项目计划书》V1.2 第 7.6–7.8、9.2–9.4、12.3 和 13 节实现。它是成员 B 的独立开发工程；占位角色用于接口验证，正式舞台由成员 C 接入。

## 先运行

**Windows：双击 `启动实验台.cmd`，保持终端窗口开启，再用 Edge / Chrome 打开 http://localhost:8765。** 摄像头仅在点击“启动摄像头”并授权后开启。不能通过双击 HTML 运行。

GitHub 提交版不包含可重新下载的运行库和关键点模型。首次运行 `npm run setup`，下载固定版本 MediaPipe 运行库、WASM 和官方 Hand Landmarker 模型到 `web/vendor/`。无业务后端、无视频上传、无 NPU 依赖。`manifest.json` 记录来源及 SHA-256。

通用环境需 Node.js 20+；在本目录运行：

```powershell
npm run setup
npm start
```

若手动删除了 `web/vendor`，联网运行 `npm run setup` 重新下载。本项目默认 CPU Worker 推理；请用最终浏览器和摄像头验证兼容性。Node 只用于本地静态文件服务，识别在浏览器本地执行。

## 第一次操作

1. 启动摄像头，确保画面里只有一只手。程序最多检测两只手，启动时多手同时出现会等待单手。
2. 可先运行约 30 秒校准：张掌、握拳、指向、捏合、舒适活动范围各 6 秒。握拳和指向只采样确认；当前只自适应捏合阈值和位置范围，角度分类阈值仍为规则默认值。
3. 张掌稳定 5 帧激活，移动手掌控制角色；握拳保持 300 ms 暂停。
4. 指向调整手臂、捏合攻击、横挥转身、快速上抬跳跃。V 手势是第 5 类静态手势的实现候选，目前仅输出 `victory`，需与成员 C 确认用途。
5. 丢手超过 125 ms 安全待机；重新张掌才能继续。切换手/参与者可点“重置控制”。停止或切到后台会关闭摄像头。
6. 摄像头不可用时，方向键移动，A 攻击、J 跳跃、T 转身、空格暂停。键盘不会混进手势采集数据。

## 已实现与待完成

| 计划步骤 | 当前交付 | 尚需真人/团队完成 |
|---|---|---|
| 第 1 天：基础推理 | 本地模型、Worker、摄像头演示、关键点和处理耗时 | 最终设备真机验证 |
| 第 2 天：事件联调 | 统一事件 SDK、占位角色 | 成员 C 接入正式舞台并确认协议 |
| 第 3 天：采集与训练 | 匿名关键点采集、数据校验、按人划分、NumPy MLP 训练和浏览器加载 | 补齐参与者和正式独立测试（P01–P04 早期实验已完成） |
| 第 4 天：稳定性 | 5 帧窗口、滞回、冷却、握拳延时、轨迹、丢手保护 | 真实误触、遮挡和多人干扰测试 |
| 第 5 天：映射校准 | 连续位置/方向/角度、30 秒校准 | 光照/距离适配验证、正式关节映射 |
| 第 6 天：性能验收 | 计时面板、观察员误触标记、报告导出、离线混淆矩阵/F1 | 完整舞台 FPS、端到端延迟、用户测试 |
| 第 7 天：交付 | 使用说明、接口说明、采样和验收步骤、故障回退 | 真实指标、模型冻结、成员 C 复核与答辩材料定稿 |

**已完成 P01–P04 早期 MLP 实验，尚未达到验收目标；权重保留在本地实验输出中，本分支只提交代码、配置和汇总指标。** 实验配置及指标见 `models/gesture/experimental/`，实验说明见 `docs/MLP实验报告.md`。 官方 Hand Landmarker 是预训练关键点模型；页面初始手势分类器是规则基线，0.85 是规则分数，不是准确率。

## 下一步：采集真实数据

详见 [采集与验收指南](docs/采集与验收.md)。已完成四人早期实验，后续补齐采样条件和参与者至计划规模。

```powershell
# 合并导出文件并用同一 JS 特征函数重新计算输入
node tools/prepare.mjs work/prepared.json data/P01.jsonl data/P02.jsonl data/P03.jsonl data/P04.jsonl data/P05.jsonl data/P06.jsonl data/P07.jsonl data/P08.jsonl
# 正式采样建议 5 人训练 + 1 人验证 + 2 人测试；命令需列全所有输入参与者
python tools/train.py work/prepared.json --train P01,P02,P03,P04,P05 --validation P06 --test P07,P08
# 验证 Python 训练与浏览器推理数值一致
node tools/check-model.mjs
```

`data/` 和 `work/` 已预建。将所有实际采集 JSONL 路径传给 prepare；如一人有多个导出文件，请把它们全部列入参数，参与者分组以文件内编号为准。Python 依赖仅 NumPy：`python -m pip install -r requirements.txt`。当前机器也可用 Codex 自带 Python。

训练结果在 `models/gesture/`：`model.json`、`report.json`、`parity.json`。页面“加载 MLP 模型”选择 `model.json`。未通过验收的模型不要替换现场规则回退。

## 测试

```powershell
npm test
python tests/test_training.py
```

算法单测包含构造输入，仅用于验证逻辑，不能当作真人数据集。当前验证记录见 [开发验证](docs/开发验证.md)。

## 接入成员 C

```js
import { GestureSDK } from './src/gesture/sdk.mjs';
const sdk = new GestureSDK(videoElement);
sdk.addEventListener('gesture', ({detail: event}) => {
  // 交给成员 C 的输入路由 / 动作状态机，勿直接播放预设剧情。
  controlRouter.accept(event);
});
await sdk.start(); // 应由用户按钮触发
// 页面卸载或结束操控时 sdk.stop()
```

保留 SDK、worker 与 `vendor` 的相对目录。React 可在 effect 清理中调用 `stop()`。协议字段与坐标约定见 [事件协议](docs/事件协议.md)。

## 目录

- `web/src/gesture/`：特征、分类、滤波、手选择、Worker 和 SDK。
- `web/`：实时页、校准、采集、占位舞台、性能报告。
- `tools/`：本地服务、模型依赖下载、数据准备、训练、跨语言推理校验。
- `tests/`：手势行为及训练数学测试。
- `docs/`：接口、采集、验收和真实开发验证记录。

## 来源

- 项目计划书：用户提供的 V1.2 PDF，第 12 页成员 B、第 13 页一周计划。
- MediaPipe Web API：[Google 官方说明](https://ai.google.dev/edge/mediapipe/solutions/vision/hand_landmarker/web_js)。
- MediaPipe 固定版本：`@mediapipe/tasks-vision@0.10.22-rc.20250304`；Hand Landmarker float16 model version 1。上游许可证随 `web/vendor/THIRD_PARTY_NOTICES.md` 记录。

## 团队仓库集成状态

本目录为独立模块，尚未接入正式舞台。团队公共契约与独立 SDK 不同，请先阅读仓库根目录 `docs/gesture-member-b-handoff.md`，不要将独立 SDK 事件直接传入正式舞台。
