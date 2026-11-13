@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion
title AI Eval Platform - 一键启动
cd /d "%~dp0"

set "APP_PORT=8001"
set "FRONTEND_PORT=5173"

if not exist "backend\run.py" goto :err_no_run
where npm >nul 2>nul
if errorlevel 1 goto :err_no_npm
if exist "backend\venv\Scripts\python.exe" set "PY=venv\Scripts\python.exe"
if not exist "backend\venv\Scripts\python.exe" set "PY=python"

echo ==========================================
echo   AI Eval Platform 一键启动
echo ==========================================
echo.
echo [配置] 后端监听 : 0.0.0.0:%APP_PORT%
echo [配置] 健康检查 : http://127.0.0.1:%APP_PORT%/api/health
echo [配置] 接口文档 : http://127.0.0.1:%APP_PORT%/docs
echo [配置] 前端访问 : http://127.0.0.1:%FRONTEND_PORT%
echo [配置] 代理转发 : /api -^> http://127.0.0.1:%APP_PORT%
echo [配置] 后端 Python: %PY%
if not exist "frontend\node_modules" echo [提示] 前端依赖未安装：请先在 frontend 目录执行 npm install，再运行本脚本。
echo.
echo [1/2] 启动后端 ...（新窗口标题含 %APP_PORT%）
start "AI-Eval Backend %APP_PORT%" cmd /k "cd /d %~dp0backend && %PY% run.py"

echo [等待] 等待后端就绪（最多 20 秒）...
set "READY=0"
for /L %%i in (1,1,20) do (
    if "!READY!"=="0" (
        curl.exe -s --max-time 2 --noproxy "*" http://127.0.0.1:%APP_PORT%/api/health 2>nul | findstr /C:"ai-eval-platform" >nul
        if not errorlevel 1 set "READY=1"
        if "!READY!"=="0" timeout /t 1 >nul
    )
)
if "!READY!"=="1" goto :backend_ready
echo.
echo [错误] 后端未在 20 秒内就绪：请查看标题含 %APP_PORT% 的后端窗口报错。
echo        常见原因：端口被其他程序占用、依赖缺失、启动异常。
echo        排查命令：netstat -ano ^| findstr ":%APP_PORT%"
echo.
goto :start_frontend

:backend_ready
echo [就绪] 后端已启动并通过健康检查（服务标识 ai-eval-platform）。

:start_frontend
echo [2/2] 启动前端 ...（新窗口标题含 %FRONTEND_PORT%）
start "AI-Eval Frontend %FRONTEND_PORT%" cmd /k "cd /d %~dp0frontend && npm run dev"
echo.
echo 两个服务已在独立窗口启动，关闭窗口即停止对应服务。
echo 若仍有接口报错，先确认后端窗口打印的监听端口与上面 [配置] 一致。
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
