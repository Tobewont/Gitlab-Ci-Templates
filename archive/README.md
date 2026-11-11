# archive

归档打包与解包：tar 系、zip、gzip。

## 能力清单

| 能力（extends） | 说明 | include 文件 |
| --- | --- | --- |
| `.archive-pack` | 文件/目录打包为归档，输出 sha256 与 dotenv | `archive/pack/jobs.gitlab-ci.yml` |
| `.archive-unpack` | 按后缀自动识别格式解包 | `archive/unpack/jobs.gitlab-ci.yml` |

## 支持格式

`ARCHIVE_PACK_FORMAT` 取值：`tar.gz`（默认）/ `tgz` / `tar.bz2` / `tbz2` / `tar.xz` / `txz` / `tar.zst` / `tar` / `zip` / `gzip`。

`gzip` 为单文件逐个压缩（产出 `<文件>.gz`，不生成归档与 sha256），其余为多文件归档。解包按文件后缀自动识别，无需配置格式。

工具由 `$CI_BASE_IMAGE` 内置（tar/gzip/zip/unzip/xz/zstd）；bzip2 或非 ci-base 镜像缺失时自动补装。

## 打包

```yaml
include:
  - project: group/gitlab-ci-templates
    ref: stable
    file: archive/pack/jobs.gitlab-ci.yml

pack:
  extends: .archive-pack
  needs: [build]
  variables:
    ARCHIVE_PACK_PATHS: "dist conf"
    ARCHIVE_PACK_BASE_DIR: "$CI_PROJECT_NAME-$CI_COMMIT_SHORT_SHA"
    ARCHIVE_PACK_EXCLUDE: "*.log"
```

输出默认为 `dist/<项目名>-<版本>.<格式>`，版本取 `ARCHIVE_PACK_VERSION` → `CI_APP_VERSION` → `CI_COMMIT_SHORT_SHA`。自定义 `ARCHIVE_PACK_OUTPUT` 指向 `ARCHIVE_PACK_OUTPUT_DIR` 之外时，须同步设置 `ARCHIVE_PACK_ARTIFACT_PATH`，否则产物不进 artifacts。

> 能力变量须配在 **job 级 `variables`**：include 进来的 `variables.gitlab-ci.yml` 默认值优先级高于业务侧 `.gitlab-ci.yml` 的全局 `variables`，写在全局不生效。

归档内路径结构二选一：

- `ARCHIVE_PACK_BASE_DIR` —— 内容收进该顶层目录，解包不散落（推荐，支持多路径）
- `ARCHIVE_PACK_STRIP` —— 剥离源路径前 N 层，仅支持单个路径；与 `BASE_DIR` 同时配置时不生效

`ARCHIVE_PACK_PATHS` 以空格分隔，路径自身不得含空格。

dotenv 导出 `CI_ARCHIVE_PATH` / `CI_ARCHIVE_NAME` / `CI_ARCHIVE_SIZE` / `CI_ARCHIVE_SHA256`，下游可直接引用：

```yaml
upload:
  extends: .package-upload
  needs: [pack]
  variables:
    UPLOAD_PACKAGE_LOCAL_PATH: "$CI_ARCHIVE_PATH"
```

## 解包

```yaml
include:
  - project: group/gitlab-ci-templates
    ref: stable
    file: archive/unpack/jobs.gitlab-ci.yml

unpack:
  extends: .archive-unpack
  variables:
    ARCHIVE_UNPACK_PATHS: "dist/app-v1.tar.gz"
    ARCHIVE_UNPACK_DEST: "release"
    ARCHIVE_UNPACK_STRIP: "1"
```

两个能力均可经 `!reference [.archive-pack, script]` / `!reference [.archive-unpack, script]` 在其它 job 内复用，不单独占一个 job。
