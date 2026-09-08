# 光影新生

AI 实时互动皮影戏台的协作工程骨架。

## 工程分层

- `packages/schemas/`：A/B/C 三方共同冻结的数据契约和 OpenAPI。
- `web/`：React + TypeScript 浏览器端应用，使用 Canvas 按 `rig.json` 渲染角色分件；B 负责手势接入，C 负责舞台和控制集成。
- `server/`：FastAPI 模型、任务和资产服务，A 负责生成 provider，C 负责 API 与资产骨架。
- `assets/`：rig、动作、材质、角色和背景资产。
- `controls/`：手势到动作、连续信号到关节的配置。
- `models/`：模型权重、标签、配置和评测说明，不提交大文件。
- `docs/`：部署、协议、评测和演示文档。
- `tests/`：跨模块契约与回放测试。
- `remote_server/`：远端昇腾服务器的可审计代码快照及兼容补丁。

## 快速启动

### 前端

需要 Node.js 18+。仓库保留了 `pnpm-workspace.yaml`，没有 pnpm 时也可以用 npm。

```bash
npm --prefix web install
npm run dev:web
```

浏览器打开 Vite 输出的地址即可进入舞台工作台，可切换角色、场景和动作，并进行关节微调。

### 重建演示资源

```bash
npm run assets:generate
```

该命令会重新生成 `assets/characters/` 下的透明角色分件和 `assets/backgrounds/` 下的舞台场景。前端与服务端共享这套资源，不再复制到 `web/public/`。

### 后端

需要 Python 3.10+。

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r server/requirements.txt
PROVIDER=mock uvicorn server.app.main:app --reload --port 8000
```

后端默认提供 `/health`、`/api/textures/generate`、`/api/tasks/{task_id}` 和 `/api/assets/{asset_id}`。

## 运行模式

```bash
PROVIDER=mock    # 固定 Mock 结果，适合前端开发
PROVIDER=cache   # 从已审核角色/背景资产读取
PROVIDER=ascend  # 预留昇腾推理接入点
```

## 远端昇腾服务器代码

服务器实际运行代码位于 [`remote_server/`](remote_server/README.md)。这是从华为云 ModelArts 服务器 `/home/ma-user/work/longcat_deploy` 获取的代码快照，运行与维护需要使用项目持有者保管的 SSH 私钥访问服务器。

仓库不保存 `KeyPair-2133.pem`、模型权重、虚拟环境、缓存和生成结果。LongCat-Image 已在 2 × Ascend 910B3 上完成 BF16、50 steps、guidance 4.0、TP=2 的真实推理验证；后续微调不得覆盖这一稳定部署。

## 协作边界

公共契约修改需要 A/B/C 共同确认。手势接入统一实现 `web/src/gesture/GestureSource.ts`，后端统一遵守 `packages/schemas/openapi.yaml`，角色包统一遵守 `rig.json` 和 `manifest.json`。
