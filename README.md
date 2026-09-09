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
PROVIDER=ascend  # 调用远端最终 LongCat LoRA，并把结果登记到 assets
```

### 调用最终 LoRA

先在华为云控制台开启 ModelArts 实例。实例处于关机状态时，任何本地程序都无法把它开机；开机后，
在仓库根目录运行下面的一键连接脚本：

```bash
./scripts/connect-longcat-api.sh /绝对路径/KeyPair-2133.pem
```

脚本会先在服务器持久盘上执行幂等恢复：核对模型与最终 LoRA、清理断电留下的陈旧 PID、启动
worker/API、等待模型就绪，然后建立本机 `127.0.0.1:8010` 的 SSH 隧道。保持该终端运行，
在另一终端启动项目后端：

```bash
PROVIDER=ascend \
ASCEND_API_BASE_URL=http://127.0.0.1:8010 \
uvicorn server.app.main:app --port 8000
```

项目后端只接受 `diffusers-lora` 与当前适配器修订
`01add392…b6898c`。背景结果会登记为待审核场景资产；人物结果会被明确标记为 `unrigged`
审核图。前者需通过中央留白和污染检查，后者必须完成透明分件和关节点标定，才能进入舞台。

## 远端昇腾服务器代码

服务器实际运行代码位于 [`remote_server/`](remote_server/README.md)。这是从华为云 ModelArts 服务器 `/home/ma-user/work/longcat_deploy` 获取的代码快照，运行与维护需要使用项目持有者保管的 SSH 私钥访问服务器。

远端模型已封装为单 worker 队列式 API。组员应使用自动恢复式 SSH 本地端口转发访问，具体请求格式、
提示词模板、断电恢复和下载方式见 [`remote_server/longcat_deploy/API使用说明.md`](remote_server/longcat_deploy/API使用说明.md)。
服务默认只监听服务器 `127.0.0.1:8010`，不应直接暴露在公网。

下一阶段的推理加速实验顺序、统一提示词、停止条件与交接提示词见
[`docs/05_下一窗口先读_昇腾LongCat推理加速交接.md`](docs/05_下一窗口先读_昇腾LongCat推理加速交接.md)。

仓库不保存 `KeyPair-2133.pem`、模型权重、虚拟环境或运行缓存。当前公开调用链固定为最终
LongCat LoRA：单卡 Ascend 910B3、BF16、50 steps、guidance 4.0、adapter scale 0.8。

## 协作边界

公共契约修改需要 A/B/C 共同确认。手势接入统一实现 `web/src/gesture/GestureSource.ts`，后端统一遵守 `packages/schemas/openapi.yaml`，角色包统一遵守 `rig.json` 和 `manifest.json`。
