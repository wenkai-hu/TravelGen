@echo off
rem ============================================================
rem  TravelGen 一键启动器（Windows）
rem  双击本文件 = 体检、起 MySQL、清端口残留、开后端和前端、开浏览器
rem  start.bat check  = 只体检不启动（排查"为什么起不来"时用，不会动已在跑的服务）
rem  【注意】本文件是 GBK 编码（配合中文控制台）。改完请另存为 ANSI/GBK，
rem          存成 UTF-8 会让 cmd 解析错位（注释行里的 > 也会被当重定向，别写箭头）。
rem ============================================================
chcp 936 >nul
setlocal
cd /d "%~dp0"
set "ROOT=%~dp0"
set "FAIL="
set "CHECKONLY="
if /i "%~1"=="check" set "CHECKONLY=1"

echo.
echo ================ TravelGen 启动器 ================
echo  项目目录: %ROOT%
echo.

rem ---------- 1) 环境体检 ----------
where python >nul 2>nul && (echo [OK] python) || (echo [X]  找不到 python，请安装 Python 并加入 PATH & set "FAIL=1")
where npm    >nul 2>nul && (echo [OK] npm)    || (echo [X]  找不到 npm，请安装 Node.js 并加入 PATH & set "FAIL=1")
if exist "backend\app.py"              (echo [OK] backend\app.py) || (echo [X]  找不到 backend\app.py，请把本脚本放在项目根目录 & set "FAIL=1")
if exist "experiments\config.json"     (echo [OK] experiments\config.json) || (echo [!]  缺少 experiments\config.json：后端没有 key 起不来。可复制 config.example.json 改名后填 key)
if exist "front\node_modules"          (echo [OK] front\node_modules) || (echo [.]  缺少 front\node_modules，正在 npm install ... & pushd front & call npm install & popd)
if defined FAIL (echo. & echo 体检未通过，已中止。 & pause & exit /b 1)

rem ---------- 2) MySQL（后端一启动就要连库）----------
sc query MySQL84 | findstr /c:"RUNNING" >nul
if errorlevel 1 (
  echo [.]  MySQL84 未运行，尝试启动 ...
  net start MySQL84 >nul 2>nul
  sc query MySQL84 | findstr /c:"RUNNING" >nul
  if errorlevel 1 (echo [X]  MySQL84 启动失败：请用"以管理员身份运行"再试，或手动 net start MySQL84 & set "FAIL=1") else (echo [OK] MySQL84 已启动)
) else (
  echo [OK] MySQL84 正在运行
)

rem ---------- 3) 端口残留（上次没关干净的 python/node）----------
call :freeport 8000 python.exe
call :freeport 5173 node.exe
if defined FAIL (echo. & echo 端口被别的程序占用，已中止。 & pause & exit /b 1)

rem ---------- 4) 启动（各自一个窗口，日志看得清）----------
if defined CHECKONLY (echo. & echo [check 模式] 体检完成，未启动服务。 & pause & exit /b 0)
echo.
echo [.]  正在启动后端（8000）...
start "TravelGen 后端 :8000" /D "%ROOT%backend" cmd /k python app.py
echo [.]  正在启动前端（5173）...
start "TravelGen 前端 :5173" /D "%ROOT%front" cmd /k npm run dev

rem ---------- 5) 等前端就绪再开浏览器 ----------
echo [.]  等待前端就绪 ...
set /a tries=0
:wait
ping -n 3 127.0.0.1 >nul
curl -s -o nul --max-time 3 http://127.0.0.1:5173/ && goto ready
set /a tries+=1
if %tries% lss 20 goto wait
echo [!]  等了约 40 秒前端仍未响应，请看"TravelGen 前端 :5173"窗口里的报错
goto done
:ready
echo [OK] 前端就绪，正在打开浏览器 ...
start "" http://127.0.0.1:5173/

:done
echo.
echo ================== 启动完成 ==================
echo   前端页面  http://127.0.0.1:5173
echo   后端接口  http://127.0.0.1:8000/api
echo   停止服务  关闭"TravelGen 后端/前端"两个窗口即可
echo   本窗口   可以直接关掉
echo ==============================================
pause
exit /b 0

rem ---------- 子过程：释放端口（只清本项目的 python/node 残留）----------
:freeport
set "PID="
for /f "tokens=5" %%p in ('netstat -ano ^| findstr /c:"LISTENING" ^| findstr /c:":%~1 "') do set "PID=%%p"
if not defined PID (echo [OK] 端口 %~1 空闲 & goto :eof)
set "PNAME="
for /f "tokens=1" %%n in ('tasklist /FI "PID eq %PID%" /NH /FO TABLE') do set "PNAME=%%n"
if defined CHECKONLY (echo [i]  端口 %~1 被 %PNAME%（PID %PID%）占用（check 模式不动它）& goto :eof)
if /i "%PNAME%"=="%~2" (
  taskkill /PID %PID% /T /F >nul 2>nul
  echo [OK] 已清掉上次残留的 %PNAME%（PID %PID%），端口 %~1 已释放
) else (
  echo [X]  端口 %~1 被 %PNAME%（PID %PID%）占用，不是本项目的进程，请手动处理后重试
  set "FAIL=1"
)
goto :eof
