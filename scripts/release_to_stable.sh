#!/usr/bin/env bash
# =============================================================================
# release_to_stable.sh —— main → stable 发布同步脚本
#
# 语义（对齐 BRANCHING.md「发布到 stable」约定）：
#   1. 以 main 的完整内容作为 stable 的新内容（同步真实变更：BRANCHING.md、mr-verdict 修复等）；
#   2. 对 examples + 所有 README 把 include 的 ref: main 批量改写为 ref: stable（发布线自洽，跳过 BRANCHING.md）；
#   3. 全程 grep 数量校验 + 断链/文档一致性校验，任一不符立即中止；
#   4. 只在本地 stable 落地一个发布提交；push 由调用方在校验通过后手动执行。
#
# 用法：
#   bash scripts/release_to_stable.sh            # 生成/更新本地 stable（不 push）
#   bash scripts/release_to_stable.sh --push     # 校验通过后自动 push origin stable
#
# 前置：工作区干净、已 git fetch、本地 main 是要发布的目标。
# =============================================================================
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

DO_PUSH="no"
[ "${1:-}" = "--push" ] && DO_PUSH="yes"

log()  { echo -e "\033[1;34m[release]\033[0m $*"; }
ok()   { echo -e "\033[1;32m[ ok ]\033[0m $*"; }
die()  { echo -e "\033[1;31m[ABORT]\033[0m $*" >&2; exit 1; }

# --- 0. 前置校验 -------------------------------------------------------------
git diff --quiet && git diff --cached --quiet || die "工作区有未提交改动，请先清理。"
CUR_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
log "当前分支: $CUR_BRANCH"

git fetch origin --prune >/dev/null 2>&1 || true

git rev-parse --verify main >/dev/null 2>&1 || die "本地缺少 main 分支。"
git rev-parse --verify origin/stable >/dev/null 2>&1 || die "缺少 origin/stable。"

MAIN_SHA="$(git rev-parse --short main)"
STABLE_SHA="$(git rev-parse --short origin/stable)"
log "main=$MAIN_SHA  origin/stable=$STABLE_SHA"

# 确认 stable 的历史是 main 的祖先分叉（正常发布拓扑：仅相差 examples ref 改写提交）
MB="$(git merge-base main origin/stable)"
log "merge-base(main, stable)=$(git rev-parse --short "$MB")"

# --- 1. 准备本地 stable：基于 origin/stable，落 main 的内容 -------------------
log "重置本地 stable 到 origin/stable ..."
git checkout -B stable origin/stable >/dev/null 2>&1
trap 'git checkout '"$CUR_BRANCH"' >/dev/null 2>&1 || true' EXIT

log "将 main 的完整内容取到 stable 工作区（同步真实变更）..."
# main 相对 stable 仅有文件内容修改（无增/删/改名，已核实），checkout -- . 即可完整对齐内容
# 只操作已跟踪文件：避免把工作区里未跟踪的本地产物（如 .work_fgui/、nul）误纳入发布
git checkout main -- .
git add -u

# --- 2. 基线校验（改写范围 = examples + 所有 README，跳过 BRANCHING.md）---------
# 仅匹配「独立成行的 include 引用行」：^\s*ref: main\s*$，天然跳过 BRANCHING.md 的叙述文字。
# grep 无匹配返回 1，配合 set -e/pipefail 会误中止；计数一律加 `|| true`。
# 目标文件：examples/**/*.gitlab-ci.yml + 仓库内所有 README.md。
mapfile -t REWRITE_FILES < <( { find examples -type f -name '*.gitlab-ci.yml'; find . -type f -name 'README.md' -not -path './.git/*' -not -path './.agnes/*' -not -path './.work_fgui/*'; } | sort -u )
log "改写目标文件数（examples + 所有 README）：${#REWRITE_FILES[@]}"
BEFORE_MAIN=$( { grep -hE "^[[:space:]]*ref: main[[:space:]]*$" "${REWRITE_FILES[@]}" || true; } | wc -l | tr -d ' ')
BEFORE_STABLE=$( { grep -hE "^[[:space:]]*ref: stable[[:space:]]*$" "${REWRITE_FILES[@]}" || true; } | wc -l | tr -d ' ')
log "改写前: ref:main=$BEFORE_MAIN  ref:stable=$BEFORE_STABLE（引用行）"
[ "$BEFORE_MAIN" -gt 0 ] || die "改写前未见 ref: main 引用行（异常）。"
ok "基线采集完成"

# --- 3. 批量改写：examples + 所有 README 的 include 引用行 ref: main -> ref: stable ---
log "改写 ref: main -> ref: stable（examples + 所有 README，仅整行引用行）..."
for f in "${REWRITE_FILES[@]}"; do
  sed -i -E 's/^([[:space:]]*)ref: main[[:space:]]*$/\1ref: stable/' "$f"
done

# --- 4. 改写后 grep 校验 -----------------------------------------------------
AFTER_MAIN=$( { grep -hE "^[[:space:]]*ref: main[[:space:]]*$" "${REWRITE_FILES[@]}" || true; } | wc -l | tr -d ' ')
AFTER_STABLE=$( { grep -hE "^[[:space:]]*ref: stable[[:space:]]*$" "${REWRITE_FILES[@]}" || true; } | wc -l | tr -d ' ')
log "改写后: ref:main=$AFTER_MAIN  ref:stable=$AFTER_STABLE（引用行）"
[ "$AFTER_MAIN" -eq 0 ] || die "改写后仍有 ref: main 引用行（预期 0）。"
[ "$AFTER_STABLE" -eq "$((BEFORE_MAIN + BEFORE_STABLE))" ] || die "ref:stable($AFTER_STABLE) != 改写前(main+stable)=$((BEFORE_MAIN + BEFORE_STABLE))。"
ok "ref 改写数量校验通过（$BEFORE_MAIN 行 ref:main -> ref:stable；总 ref:stable=$AFTER_STABLE）"

# --- 5. 内容一致性校验（真实变更已同步）-------------------------------------
# 5a. BRANCHING.md 不应再出现 ref: main（同步 main 三线版后应改写为 ref: stable 语境）
if grep -n "ref: main" BRANCHING.md >/dev/null 2>&1; then
  echo "  [warn] BRANCHING.md 仍含 'ref: main' 字样，请人工确认是否为说明性文字："
  grep -n "ref: main" BRANCHING.md || true
fi
# 5b. mr-verdict-usage 断链修复应已随内容带入：本地锚点 .mr-always/.on-k8s 存在
if [ -f examples/mr-verdict-usage.gitlab-ci.yml ]; then
  grep -q "^\.mr-always:" examples/mr-verdict-usage.gitlab-ci.yml \
    && grep -q "^\.on-k8s:" examples/mr-verdict-usage.gitlab-ci.yml \
    || die "mr-verdict-usage 缺少本地锚点 .mr-always/.on-k8s（断链未修复）。"
  ok "mr-verdict-usage 断链修复已同步（本地锚点存在，ref 已为 stable）"
fi

# --- 6. 暂存并提交 -----------------------------------------------------------
git add -u
if git diff --cached --quiet; then
  log "stable 内容与 origin/stable 无差异，无需发布提交。"
  git checkout "$CUR_BRANCH" >/dev/null 2>&1 || true
  trap - EXIT
  exit 0
fi

log "本次发布提交将包含以下文件变更（相对 origin/stable）："
git diff --cached --name-status | sed 's/^/    /'

COMMIT_MSG="$(mktemp -t release_msg.XXXXXX)"
cat > "$COMMIT_MSG" <<EOF
release(stable): promote main($MAIN_SHA) -> stable

同步 main 真实变更并保持发布线 examples 自洽引用 ref: stable：
- BRANCHING.md: 同步三线分支模型与"发布到 stable"约定
- examples/mr-verdict-usage.gitlab-ci.yml: 同步 .mr-always/.on-k8s 本地锚点断链修复
- examples/ + 所有 README: ref: main -> ref: stable 批量改写（$BEFORE_MAIN 行）+ 校验通过
EOF
git commit -F "$COMMIT_MSG" >/dev/null
NEW_STABLE="$(git rev-parse --short HEAD)"
ok "已在本地 stable 生成发布提交: $NEW_STABLE"

# --- 7. 最终复核 -------------------------------------------------------------
# 7a. 直接跑 stable 引用门禁脚本：examples + 所有 README 不得有 ref: main 引用行
log "复核: 运行 stable-ref-guard 校验脚本（examples + 所有 README）..."
# 选可用的 Python：优先 python3；若无法真正运行（如 Windows launcher 损坏）则回退 python
PYBIN=""
for cand in python3 python; do
  if command -v "$cand" >/dev/null 2>&1 && "$cand" -c "import sys" >/dev/null 2>&1; then PYBIN="$cand"; break; fi
done
[ -n "$PYBIN" ] || die "未找到可运行的 Python（python3/python）。"
"$PYBIN" scripts/check_stable_refs.py --root . || die "stable 引用红线未通过：examples/README 仍有 ref: main 引用行。"
# 7b. 与 main 的差异只应是「ref 行」+「BRANCHING 说明性文字」，无 example/README 逻辑差异
log "复核: 本地 stable vs main，examples+README 非 ref 行差异（应为 0）："
NONREF=$( { git diff stable main -- examples/ '*README.md' | grep -E '^[+-]' | grep -vE '^(\+\+\+|---)' \
         | grep -vE '^[+-][[:space:]]*ref: (main|stable)[[:space:]]*$' || true; } | wc -l | tr -d ' ')
echo "    examples+README 非 ref 行差异数: $NONREF"
[ "$NONREF" -eq 0 ] || { git diff stable main -- examples/ '*README.md' | grep -E '^[+-]' | grep -vE '^(\+\+\+|---)' | grep -vE '^[+-][[:space:]]*ref: (main|stable)[[:space:]]*$'; die "stable 与 main 存在非 ref 的 examples/README 逻辑差异，请人工核查。"; }
ok "复核通过：stable 与 main 仅剩 examples/README 的 ref 差异（设计内分叉）"

# --- 8. push（可选）----------------------------------------------------------
if [ "$DO_PUSH" = "yes" ]; then
  log "推送 origin stable ..."
  git push origin stable
  ok "已推送 origin stable = $NEW_STABLE"
else
  echo
  ok "本地 stable 已就绪（未推送）。确认无误后执行： git push origin stable"
fi

git checkout "$CUR_BRANCH" >/dev/null 2>&1 || true
trap - EXIT
log "完成。已切回 $CUR_BRANCH。"
