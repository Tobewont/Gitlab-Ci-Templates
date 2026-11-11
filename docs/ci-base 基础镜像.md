# ci-base 通用基础镜像

> 镜像：`registry.example.com/cicd/ci-base:alpine3.23.5`
> Dockerfile：仓库根目录 `Dockerfile.ci-base`
> 用途：`CI_BASE_IMAGE` 默认值，承载 notify / common / git / checks / security / deploy / upload / quality 等轻量胶水类原子能力。

## 背景

旧 `CI_BASE_IMAGE`（`curlimages/curl:8.1.1`）只有 curl，部分原子能力用 `git`、`jq`、`nc` 等命令时会报"找不到命令"。本镜像基于 `alpine:3.23.5` 补齐 CI 常用工具，作为模板层通用基础镜像。

语言编译环境**不进**此镜像（go/node/java/gcc 等仍走 `build/*` 能力的专用镜像），本镜像只承担通知、检查、git 操作、部署、上传等胶水任务。

## 包含工具

| 类别 | 工具 |
|---|---|
| Shell/系统 | bash、coreutils、grep、sed、gawk、findutils、diffutils、procps、tzdata、less |
| 网络/传输 | curl、wget、nc(netcat-openbsd)、ssh/scp/sftp(openssh-client)、sshpass、rsync、lftp、ping(iputils)、nslookup/dig(bind-tools)、openssl、ca-certificates |
| 压缩/归档 | tar(自带)、zip、unzip、xz、zstd |
| 数据处理 | jq、yq、envsubst(gettext)、xmlstarlet |
| VCS | git、git-lfs |
| 胶水语言 | python3、pip3 |
| 部署 | docker-cli、kubectl、helm |

默认环境：`LANG=en_US.UTF-8`、`TZ=Asia/Shanghai`。构建期含自检，缺命令直接 build 失败。

## 构建与推送

```bash
# 在仓库根目录执行
docker build -f Dockerfile.ci-base -t registry.example.com/cicd/ci-base:alpine3.23.5 .
docker push registry.example.com/cicd/ci-base:alpine3.23.5

# 国内 apk 源慢时加构建参数
docker build -f Dockerfile.ci-base --build-arg APK_MIRROR=mirrors.aliyun.com \
  -t registry.example.com/cicd/ci-base:alpine3.23.5 .
```

## 使用与回滚

- `base/variables.gitlab-ci.yml` 的 `CI_BASE_IMAGE` 默认即此镜像，业务项目一般无需配置。
- 个别 job 如需特定镜像，业务侧覆盖 `CI_BASE_IMAGE` 即可（变量驱动，不改模板）。
- 回滚旧镜像：业务侧临时设 `CI_BASE_IMAGE: "registry.example.com/library/curlimages/curl:8.1.1"`。

## 版本策略

tag 与 alpine 版本对齐（`alpine3.23.5`）。工具集变更需升级时，追加后缀（如 `alpine3.23.5-r1`）并在 `CI_BASE_IMAGE` 默认值中切换，保留旧 tag 便于回滚。
