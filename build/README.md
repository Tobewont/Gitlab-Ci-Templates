# build

多语言构建：C++/Go/Java/Node/Android/Docker/protobuf/Cocos/Windows。

## 能力清单

| 能力（extends） | 说明 | include 文件 |
| --- | --- | --- |
| `.channel-package` | - | `build/android/jobs.gitlab-ci.yml` |
| `.cmake-build` | - | `build/cpp/jobs.gitlab-ci.yml` |
| `.cocos-build` | - | `build/cocos/jobs.gitlab-ci.yml` |
| `.cocos-build-windows` | Windows PowerShell 版本（Windows Cocos runner） | `build/cocos/jobs.gitlab-ci.yml` |
| `.docker-build` | 默认：走宿主 docker.sock | `build/docker/jobs.gitlab-ci.yml` |
| `.docker-build-dind` | 备用：dind 方式 | `build/docker/jobs.gitlab-ci.yml` |
| `.go-build` | - | `build/go/jobs.gitlab-ci.yml` |
| `.make-build` | 默认跑 make，可用 BUILD_CPP_MAKE_SCRIPT 覆盖为任意构建命令 | `build/cpp/jobs.gitlab-ci.yml` |
| `.maven-build` | - | `build/java/jobs.gitlab-ci.yml` |
| `.msbuild` | MSBuild（Visual Studio 编译 .NET / C++ 项目） | `build/windows/jobs.gitlab-ci.yml` |
| `.node-build` | - | `build/nodejs/jobs.gitlab-ci.yml` |
| `.node-build-windows` | Windows PowerShell 版本 | `build/nodejs/jobs.gitlab-ci.yml` |
| `.protoc-gen` | - | `build/protobuf/jobs.gitlab-ci.yml` |
| `.windows-bat` | 通用 Windows .bat 脚本执行 | `build/windows/jobs.gitlab-ci.yml` |

## 用法

按上表 include 目标能力所属文件，再 `extends` 对应能力：

```yaml
include:
  - project: group/gitlab-ci-templates
    ref: stable
    file: build/android/jobs.gitlab-ci.yml
```

能力开关与参数默认值见同目录 `variables.gitlab-ci.yml`。
