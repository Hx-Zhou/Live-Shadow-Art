# 远端昇腾服务器代码

本目录保存的是部署在华为云 ModelArts 远端服务器上的代码快照，不是本地可直接运行的完整环境。

## 访问方式

服务器工作目录：`/home/ma-user/work/longcat_deploy`

需要使用项目持有者保管的 SSH 私钥访问：

```bash
ssh -o StrictHostKeyChecking=no -i KeyPair-2133.pem \
  -o UserKnownHostsFile=/dev/null \
  ma-user@dev-modelarts.cn-southwest-2.huaweicloud.com -p 32584
```

`KeyPair-2133.pem` 属于私密凭据，不在本仓库中，也不得提交到 Git。

## 快照范围

- `longcat_deploy/root/`：远端工作目录下的自研部署、验证和批量生成脚本。
- `longcat_deploy/root/api_service/`：真实 NPU 模型的持久 worker 与队列式 HTTP API。
- `longcat_deploy/project/`：提示词、测试、基准工具和服务器执行说明。
- `longcat_deploy/patches/`：对固定上游版本所做的本地兼容补丁。
- `longcat_deploy/UPSTREAM_VERSIONS.md`：服务器上三个上游仓库的固定提交号。

以下内容有意排除：模型权重、虚拟环境、wheel、缓存、生成结果、安装日志、运行日志、SSH 密钥和访问令牌。

## 使用原则

此目录是服务器代码的可审计快照。服务器仍是实际 NPU 运行环境；在本地修改代码后，应先审查差异，再通过 SSH 同步到独立测试目录。不要直接覆盖服务器上已验证通过的稳定部署。

组员调用模型时应按 [`longcat_deploy/API使用说明.md`](longcat_deploy/API使用说明.md) 建立 SSH
隧道。API 默认不监听公网地址，仓库不提供也不保存真实私钥或令牌。
