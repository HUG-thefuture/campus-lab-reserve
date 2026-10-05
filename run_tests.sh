#!/usr/bin/env bash
# =====================================================================
# 一键测试脚本（Linux/macOS/Windows Git Bash 通用）
# 用法：在 project/ 目录执行  bash run_tests.sh
# 作用：设置 PYTHONPATH=vendor 后运行 pytest（conftest 会自行启动真实
#       uvicorn 子进程并在每个用例前重置 SQLite）
# =====================================================================
set -e
Base="$(cd "$(dirname "$0")" && pwd)"

# 1. 离线依赖目录 vendor 通过 PYTHONPATH 提供（不污染全局环境）
export PYTHONPATH="$Base/vendor"
export PYTHONIOENCODING=utf-8

# 2. 兼容不同平台：逐个探测可用的 Python（Windows 上 python3 可能是商店空壳别名）
PY=""
for cand in python3 python; do
  if "$cand" -c "import sys" >/dev/null 2>&1; then PY="$cand"; break; fi
done
[ -n "$PY" ] || { echo "错误：未找到可用的 Python 解释器" >&2; exit 1; }

# 3. 运行 pytest（-p no:cacheprovider 避免缓存目录写入问题）
echo "==> 运行接口自动化测试（lab_reserve:8010 / study_checkin:8011 的测试实例）..."
"$PY" -m pytest "$Base/tests" -v --tb=short -p no:cacheprovider

echo ""
echo "==> 完成。全部通过即表示两个应用的接口行为与简历承诺一致。"
