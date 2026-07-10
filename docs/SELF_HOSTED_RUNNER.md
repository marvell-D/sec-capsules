# 腾讯云自托管 GitHub Actions Runner 运维说明

本仓库的 CI 不是运行在 GitHub 托管机器上，而是运行在腾讯云 Linux 服务器注册的 GitHub Actions self-hosted runner 上。本文件解释它是什么、当前部署在哪里、workflow 怎样调度到它，以及日常怎样检查和维护。

本文不包含 GitHub registration token、runner 凭据或任何私钥。它们只能保存在服务器或 GitHub Secrets 中，绝不能提交到仓库。

## 1. 什么是 CI/CD

**CI（Continuous Integration，持续集成）**：每次 push 或 Pull Request 自动在干净的工作目录中安装项目、编译并测试。它回答的是“这次提交能否与主线一起正常工作”。

**CD** 有两种常见含义：

- **持续交付（Continuous Delivery）**：CI 成功后自动构建一个可交付产物，由人决定何时发布。
- **持续部署（Continuous Deployment）**：CI 成功后自动发布到生产环境。

当前 `sec-capsules` 实现的是 **CI + 持续交付**：普通 workflow 成功后上传 wheel 和 source distribution artifact；并未自动上传 PyPI，也没有自动部署公网服务。`Local E2E` 是手动运行的受控验证，不属于自动生产部署。

## 2. 为什么使用 self-hosted runner

安全工具 Runtime 的 E2E 需要 Docker、`httpx`、`katana`、`nuclei` 等外部二进制，并且只能在受控靶场执行。自托管 runner 使项目能够：

- 管理外部工具版本与本机 Docker 环境。
- 将 Juice Shop 容器只绑定到 `127.0.0.1`，避免暴露为公网靶场。
- 把网络、磁盘、日志和执行权限放在项目可审计的服务器中。
- 避免把未经验证的安全工具任务直接交给公共 runner。

代价是维护责任在项目方：runner 执行仓库 workflow 中的 shell 命令，因此只有受信任贡献者的代码才应获得可在此 runner 上运行的权限。

## 3. 当前部署事实

截至 v0.1.1，项目使用的真实路径与服务如下：

```text
腾讯云服务器仓库： /home/ubuntu/git/sec-capsules
Actions Runner 目录： /home/ubuntu/actions-runner
systemd 服务：      actions.runner.marvell-D-sec-capsules.sec-capsules-tencent.service
Runner 标签：       self-hosted, Linux, X64, tencent, sec-capsules
```

系统级工具位于 `/usr/local/bin`，已安装并用于本机 E2E 的版本为：

```text
httpx   v1.10.0
katana  v1.6.1
nuclei  v3.11.0
```

Nuclei 的默认模板初始化目录为 `/home/ubuntu/nuclei-templates`。日常 E2E 采用仓库内单个 `local-juice-shop.yaml` 模板，避免在 CI 中加载完整的默认模板集。

## 4. Workflow 如何找到这台机器

普通 CI 定义在 `.github/workflows/ci.yml`：

```yaml
jobs:
  test:
    runs-on: [self-hosted, linux]
```

`runs-on` 是标签匹配条件。GitHub 收到 push 或 PR 后，会查找同时满足 `self-hosted` 与 `linux` 标签且在线的 runner；当前腾讯 runner 满足条件，便会领取 job。

`test` job 成功后，`package` job 因 `needs: test` 才会开始。两者实际步骤为：

```text
GitHub 事件（push / pull_request）
    -> 腾讯 runner 领取 test job
    -> actions/checkout@v4 检出该提交
    -> actions/setup-python@v5 准备 Python 3.12
    -> pip install -e .
    -> scripts/ci.sh
         -> python -m compileall src tests
         -> python -m unittest discover -s tests -v
    -> test 通过后领取 package job
    -> python -m build
    -> 上传 dist/*.whl 和 dist/*.tar.gz 为 GitHub artifact
```

`Local E2E` 定义在 `.github/workflows/e2e-local.yml`，触发器只有 `workflow_dispatch`，因此不会随着 push 自动扫描：

```text
人工在 GitHub Actions 页面点击 Run workflow
    -> runner 检出代码、安装 editable package
    -> scripts/e2e-local.sh
         -> docker compose 启动仅本机绑定的 Juice Shop
         -> curl 等待 http://127.0.0.1:3000 就绪
         -> sec-capsules doctor --require
         -> 运行 web-recon-local-lab Recipe
         -> trap 清理 Docker 容器
    -> 无论成功或失败，上传 runs-e2e/ artifact
```

## 5. 首次注册一台 runner

以下命令是概念性步骤。注册 token 从 GitHub 仓库的 `Settings -> Actions -> Runners -> New self-hosted runner` 临时获取，勿复制到文档、终端历史共享记录或 git。

```bash
mkdir -p ~/actions-runner
cd ~/actions-runner

# 下载链接和文件名以 GitHub 当时展示的 Linux x64 指令为准。
curl -L -o actions-runner-linux-x64.tar.gz <github-runner-download-url>
tar xzf actions-runner-linux-x64.tar.gz

./config.sh \
  --url https://github.com/marvell-D/sec-capsules \
  --token <runner-registration-token> \
  --labels tencent,sec-capsules \
  --unattended

sudo ./svc.sh install
sudo ./svc.sh start
```

不要手工伪造 `self-hosted`、`Linux`、`X64` 等系统标签；runner 会自动报告它们。注册后，应在 GitHub 的 `Settings -> Actions -> Runners` 页面确认状态为 `Idle` 或 `Active`，而不是 `Offline`。

## 6. 日常检查与故障排查

在腾讯云服务器上执行：

```bash
# Runner 服务状态
sudo systemctl status actions.runner.marvell-D-sec-capsules.sec-capsules-tencent.service

# 实时查看 runner 日志
sudo journalctl -u actions.runner.marvell-D-sec-capsules.sec-capsules-tencent.service -f

# 服务异常后的重启
sudo systemctl restart actions.runner.marvell-D-sec-capsules.sec-capsules-tencent.service

# 外部工具和 Docker 的本机健康检查
httpx -version
katana -version
nuclei -version
docker --version
docker compose version

# 在真实仓库副本中运行与 CI 相同的基础验证
cd /home/ubuntu/git/sec-capsules
scripts/ci.sh
```

当 GitHub Actions 显示 job 排队而不是开始时，先检查 GitHub runner 页面是否离线，再看 systemd 状态和 runner 日志。测试失败时，先下载 Actions 日志或在 `/home/ubuntu/git/sec-capsules` 复现相同命令；不要为了让 workflow 变绿而跳过测试或删除 Scope 检查。

## 7. 运行和查看 workflow

普通 CI 在 push 后自动运行。`Local E2E` 必须从 GitHub 仓库的 `Actions -> Local E2E -> Run workflow` 手动触发。成功的 job 会在 GitHub Actions 页面保存：

- `sec-capsules-dist`：普通 CI 的 wheel / source distribution。
- `local-e2e-runs`：本机靶场运行的 `run.json`、structured result、Observation 与 artifact 元数据。

artifact 是验证输出，不是长期日志数据库；保留天数由 GitHub 仓库配置决定。需要长期留存的审计结果应由后续版本接入专门的存储策略，而不是依赖 runner 工作目录。

## 8. 运维与安全检查单

- runner 用户不要拥有不必要的云账号、生产密钥或个人 SSH agent。
- 限制能触发可写 workflow 的 GitHub 权限，审查来自 fork 的 PR 设置。
- 定期升级 Actions runner、Python、Docker 和 ProjectDiscovery 工具，并在升级后跑 `scripts/ci.sh` 与本机 E2E。
- 对安装的 release 二进制校验官方 checksum；不要执行来历不明的安装脚本。
- E2E 仅允许本机靶场，并让 compose 端口绑定 `127.0.0.1`。
- 清理失败 job 遗留的容器、`runs-e2e/` 和大体积 artifact，同时保留必要审计信息。
- 不将 runner registration token、`.runner` 凭据、GitHub PAT、目标资产清单或真实扫描 artifact 提交到仓库。

自托管 runner 是执行边界的一部分，但不是完整沙箱。外部工具仍以 runner 用户身份运行，生产级部署还应增加网络 egress 限制、隔离账户和更严格的审批系统。
