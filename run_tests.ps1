# =====================================================================
# 一键测试脚本（Windows PowerShell）
# 用法：在 project/ 目录执行  .\run_tests.ps1
# 作用：设置 PYTHONPATH=vendor 后运行 pytest（conftest 自行启动 uvicorn
#       子进程，并在每个用例前重置 SQLite）
# =====================================================================
$ErrorActionPreference = "Stop"
$Base = Split-Path -Parent $MyInvocation.MyCommand.Path

# 1. 离线依赖目录 vendor 通过 PYTHONPATH 提供
$env:PYTHONPATH = (Join-Path $Base "vendor")
$env:PYTHONIOENCODING = "utf-8"

# 2. 运行 pytest
Write-Host "==> 运行接口自动化测试（lab_reserve / study_checkin 测试实例）..."
python -m pytest (Join-Path $Base "tests") -v --tb=short -p no:cacheprovider

Write-Host ""
Write-Host "==> 完成。全部通过即表示两个应用的接口行为与简历承诺一致。"
