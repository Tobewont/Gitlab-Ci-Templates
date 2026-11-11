# notify

通知：聚合入口 + 飞书 / 企微 / 钉钉 / webhook，均为机器人直连。

## 能力清单

| 能力（extends） | 说明 | include 文件 |
| --- | --- | --- |
| `.notify` | NOTIFY_CHANNEL 默认 feishu，可逗号多选 | `notify/jobs.gitlab-ci.yml` |
| `.notify-base` | ── 公共基座（独立 notify job 用）：查状态 + 组装消息 ────────────── | `notify/jobs.gitlab-ci.yml` |
| `.notify-build-message` | ③ 消息组装编排：逐层引用文案层片段，本身不含文案 | `notify/jobs.gitlab-ci.yml` |
| `.notify-dingtalk` | 原子能力：钉钉自定义群机器人通知 | `notify/dingtalk/jobs.gitlab-ci.yml` |
| `.notify-feishu` | 飞书自定义机器人 | `notify/feishu/jobs.gitlab-ci.yml` |
| `.notify-feishu-bot` | 与 `.notify-feishu` 相同 | `notify/feishu/jobs.gitlab-ci.yml` |
| `.notify-inline` | 放进 `after_script`。状态取 `NOTIFY_STATUS_OVERRIDE`，否则取 `CI_JOB_STATUS`；该值为 running 或空时再读 `.notify-status`，没有则记失败 | `notify/jobs.gitlab-ci.yml` |
| `.notify-mark-success` | 在 script 末尾写入 `.notify-status=success`，供 `.notify-inline` 在 `CI_JOB_STATUS` 仍为 running 时使用 | `notify/jobs.gitlab-ci.yml` |
| `.notify-preheat` | 预告通知。默认阶段 `.pre`，不查状态。渠道 `NOTIFY_PREHEAT_CHANNEL`，地址与 `.notify` 相同 | `notify/jobs.gitlab-ci.yml` |
| `.notify-restart-notice` | `.notify-preheat` 的服务重启场景别名，文案自动组装 | `notify/jobs.gitlab-ci.yml` |
| `.notify-resolve-api` | ① 状态判定（独立 job 场景：查 GitLab API） | `notify/jobs.gitlab-ci.yml` |
| `.notify-resolve-inline` | ② 状态判定（after_script 内嵌场景） | `notify/jobs.gitlab-ci.yml` |
| `.notify-send-channels` | 按渠道把正文 POST 到对应 webhook | `notify/jobs.gitlab-ci.yml` |
| `.notify-webhook` | POST `{"text": "<标题与正文>"}` 到 `NOTIFY_WEBHOOK_URL` | `notify/webhook/jobs.gitlab-ci.yml` |
| `.notify-wework` | 原子能力：企业微信自定义群机器人通知 | `notify/wework/jobs.gitlab-ci.yml` |

## 用法

按上表 include 目标能力所属文件，再 `extends` 对应能力：

```yaml
include:
  - project: group/gitlab-ci-templates
    ref: stable
    file: notify/jobs.gitlab-ci.yml
```

能力开关与参数默认值见同目录 `variables.gitlab-ci.yml`。

## 文案层

通知文案按场景拆分到 `notify/message/`，改某场景文案只改对应文件，不影响其他场景：

| 文件 | 片段 | 覆盖场景 |
| --- | --- | --- |
| `notify/message/common.gitlab-ci.yml` | `.notify-msg-fields` / `.notify-msg-default` / `.notify-msg-render` / `.notify-msg-labels` | 公共字段、正文骨架、模板渲染、JSON 转义 |
| `notify/message/pipeline.gitlab-ci.yml` | `.notify-msg-pipeline` / `.notify-msg-build` / `.notify-msg-upload` / `.notify-msg-download` | 流水线（兼未知场景兜底）/ 构建 / 制品上传 / 制品下载 |
| `notify/message/deploy.gitlab-ci.yml` | `.notify-msg-deploy` | 部署 |
| `notify/message/scan.gitlab-ci.yml` | `.notify-msg-scan` | 代码扫描 |
| `notify/message/review.gitlab-ci.yml` | `.notify-msg-review` | 代码评审 |
| `notify/message/compliance.gitlab-ci.yml` | `.notify-msg-compliance` | 合规检测（正文整条自定义） |
| `notify/message/smoke.gitlab-ci.yml` | `.notify-msg-smoke` | 冒烟测试 |
| `notify/message/preheat.gitlab-ci.yml` | `.notify-msg-preheat` | 预告通知 |

场景片段各自带 `NOTIFY_SCENARIO` 守卫，`.notify-build-message` 按顺序引用全部场景片段，
运行期只有命中的那一个赋值。
