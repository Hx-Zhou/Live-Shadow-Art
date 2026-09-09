# P05 / P06 增量数据实验

`p05-2026-09-09/` 和 `p06-2026-09-09/` 保存训练脚本与完整汇总指标。每轮从随机种子 42 重新训练，未接着旧权重迭代。P03 验证集不变，本轮没有重新评测 P04。

| 版本 | 训练参与者 | 训练帧 | P03 Macro-F1（0.70 / 0.75） |
|---|---|---:|---|
| P05 | P01、P02、P05 | 2521 | 0.6297 / 0.5917 |
| P06 | P01、P02、P05、P06 | 3268 | 0.6972 / 0.6630 |

`p06-2026-09-09/model.json` 是最新最佳权重，前端文件加载入口可直接选择。加载后门槛仍为默认 0.75。模型尚未验收，0.70 门槛下握拳仅识别对 16/98 帧、单指 9/98 帧。P03 被重复用于模型选择，不能以验证结果替代新参与者测试。

## 复现

需要 Node.js、Python 和 NumPy（安装模块 requirements.txt）。在 `modules/gesture-b/` 目录执行：

```sh
node tools/prepare.mjs models/gesture/experimental/p06-2026-09-09/prepared.json <P01-P04导出.jsonl> <包含P05和P06的最新导出.jsonl>
python models/gesture/experimental/p06-2026-09-09/train_p06.py
node tools/check-model.mjs models/gesture/experimental/p06-2026-09-09/model.json models/gesture/experimental/p06-2026-09-09/parity.json
```

原始数据由采集者本地保管，不在仓库中；需要获得同一批数据才能精确复现。上述命令会重写实验目录中的 model.json/report.json，并生成 prepared.json/parity.json。训练脚本旁的 trainer_snapshot.py 固定了本次所用梯度和指标实现。

P05 复现方式相同，将路径和脚本换为 P05，并仅输入 P01–P04 与 P05 数据。原始导出文件名与数据哈希见本地审计及各 report.json；P06 处理后数据 SHA-256 为 `94217d38a98e112f563721c6515832d2cec7be88a4e3cd8b20b21315e8ba4fad`。

本次 Python / JavaScript 核对六个类别各一个样本，6 项全部通过。逐帧数据、特征核对样本和第三方运行资源不纳入提交。旧 candidate-config.json / comparison.json 记录早期实验，最新状态以 STATUS.json 与本目录 P06 report.json 为准。
