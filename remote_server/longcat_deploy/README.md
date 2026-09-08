# LongCat-Image 远端部署代码快照

- 来源服务器：华为云 ModelArts（通过项目 SSH 入口访问）
- 来源路径：`/home/ma-user/work/longcat_deploy`
- 快照日期：2026-09-08（Asia/Shanghai）
- 运行硬件：2 × Ascend 910B3
- 已验证推理基线：BF16、50 steps、guidance 4.0、TP=2

这个快照用于记录远端服务器的实际代码及兼容修改。它不包含约 29GB 的 LongCat-Image 模型，也不包含 CANN、Python 虚拟环境、运行缓存或生成图片。

根目录脚本在仓库中位于 `root/`，同步回服务器时应恢复到 `/home/ma-user/work/longcat_deploy/`。`project/` 的相对目录结构保持不变。

上游源码不重复镜像到本仓库。应检出 `UPSTREAM_VERSIONS.md` 指定的提交，然后依次应用 `patches/` 中的补丁。

