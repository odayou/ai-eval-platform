@echo off
chcp 65001 >nul
title AI Eval Platform
cd /d "%~dp0"

if not exist "backend\run.py" goto :err_no_run
if exist "backend\venv\Scripts\python.exe" set "PY=venv\Scripts\python.exe"
if not exist "backend\venv\Scripts\python.exe" set "PY=python"
where npm >nul 2>nul
if errorlevel 1 goto :err_no_npm

echo ==========================================
echo   AI Eval Platform 一键启动
echo ==========================================
echo.
echo [检查] 后端 Python: %PY%
if not exist "frontend\node_modules" echo [提示] 前端依赖未安装：请先在 frontend 目录执行 npm install，再运行本脚本。
echo.
echo [1/2] 启动后端 ...（新窗口标题：AI-Eval Backend）
start "AI-Eval Backend" cmd /k "cd /d %~dp0backend && %PY% run.py"
echo [2/2] 启动前端 ...（新窗口标题：AI-Eval Frontend）
start "AI-Eval Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"
echo.
echo 两个服务已在独立窗口启动，关闭窗口即停止对应服务。
echo 如果某个窗口里有报错，日志会停留在窗口里，把内容发我即可。
echo.
pause
exit /b 0

:err_no_run
echo [错误] 未找到 backend\run.py，请在项目根目录运行本脚本。
pause
exit /b 1

:err_no_npm
echo [错误] 未检测到 npm，请先安装 Node.js 并加入 PATH。
pause
exit /b 1
