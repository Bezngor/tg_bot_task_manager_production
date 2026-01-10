# Скрипт для перезапуска всех сервисов на localhost (бот, API, админ-панель)
# PowerShell скрипт для Windows

$ErrorActionPreference = "Stop"

# Получаем директорию скрипта
$SCRIPT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $SCRIPT_DIR

Write-Host "=== Перезапуск всех сервисов на localhost ===" -ForegroundColor Cyan
Write-Host ""

# Функция для остановки процесса по имени модуля или порту
function Stop-ServiceByModule {
    param(
        [string]$ModuleName,
        [string]$DisplayName,
        [int]$Port = 0
    )
    
    Write-Host "Остановка $DisplayName..." -ForegroundColor Yellow
    
    $stopped = $false
    
    # Способ 1: Поиск по порту (более надежно для API и админ-панели)
    if ($Port -gt 0) {
        try {
            $connections = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
            foreach ($conn in $connections) {
                try {
                    $process = Get-Process -Id $conn.OwningProcess -ErrorAction SilentlyContinue
                    if ($process) {
                        Write-Host "  Найден процесс на порту $Port (PID $($process.Id))" -ForegroundColor Gray
                        Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
                        $stopped = $true
                        Start-Sleep -Milliseconds 500
                    }
                } catch {
                    # Игнорируем ошибки
                }
            }
        } catch {
            # Get-NetTCPConnection может быть недоступна, продолжаем другим способом
        }
    }
    
    # Способ 2: Поиск по command line в процессах Python
    $allPythonProcesses = Get-Process python -ErrorAction SilentlyContinue
    foreach ($proc in $allPythonProcesses) {
        try {
            $commandLine = (Get-CimInstance Win32_Process -Filter "ProcessId = $($proc.Id)" -ErrorAction SilentlyContinue).CommandLine
            if ($commandLine -and $commandLine -like "*$ModuleName*") {
                Write-Host "  Найден процесс PID $($proc.Id): $($commandLine.Substring(0, [Math]::Min(80, $commandLine.Length)))" -ForegroundColor Gray
                Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
                $stopped = $true
                Start-Sleep -Milliseconds 500
            }
        } catch {
            # Игнорируем ошибки
        }
    }
    
    if ($stopped) {
        Write-Host "  $DisplayName остановлен" -ForegroundColor Green
    } else {
        Write-Host "  $DisplayName не найден (возможно, уже остановлен)" -ForegroundColor Gray
    }
}

# Функция для запуска сервиса
function Start-Service {
    param(
        [string]$ModuleName,
        [string]$DisplayName,
        [string]$LogFile = $null
    )
    
    Write-Host "Запуск $DisplayName..." -ForegroundColor Yellow
    
    # Проверяем наличие виртуального окружения
    $venvPython = Join-Path $SCRIPT_DIR "venv\Scripts\python.exe"
    if (Test-Path $venvPython) {
        $pythonExe = $venvPython
    } else {
        $pythonExe = "python"
    }
    
    # Запускаем процесс в фоновом режиме
    try {
        # Создаем папку для логов, если нужно
        if ($LogFile) {
            $logDir = Join-Path $SCRIPT_DIR "logs"
            if (-not (Test-Path $logDir)) {
                New-Item -ItemType Directory -Path $logDir -Force | Out-Null
            }
        }
        
        # Запускаем процесс в новом окне (скрытом)
        $processArgs = @{
            FilePath = $pythonExe
            ArgumentList = @("-m", $ModuleName)
            WindowStyle = "Hidden"
            PassThru = $true
            WorkingDirectory = $SCRIPT_DIR
        }
        
        $process = Start-Process @processArgs
        
        if ($process) {
            Start-Sleep -Seconds 2
            Write-Host "  $DisplayName запущен (PID: $($process.Id))" -ForegroundColor Green
        } else {
            Write-Host "  Предупреждение: не удалось получить PID процесса" -ForegroundColor Yellow
        }
    } catch {
        Write-Host "  Ошибка при запуске: $_" -ForegroundColor Red
        throw
    }
}

# Шаг 1: Остановка всех сервисов
Write-Host "--- Шаг 1: Остановка сервисов ---" -ForegroundColor Cyan
Write-Host ""

Stop-ServiceByModule "app.bot.bot" "Telegram бот" 0
Stop-ServiceByModule "app.api.api" "API сервер" 5050
Stop-ServiceByModule "app.admin.admin_panel" "Админ-панель" 5051

Write-Host ""
Write-Host "Ожидание завершения процессов..." -ForegroundColor Yellow
Start-Sleep -Seconds 2
Write-Host ""

# Шаг 2: Запуск всех сервисов
Write-Host "--- Шаг 2: Запуск сервисов ---" -ForegroundColor Cyan
Write-Host ""

Start-Service "app.bot.bot" "Telegram бот" "bot.log"
Start-Service "app.api.api" "API сервер" "api.log"
Start-Service "app.admin.admin_panel" "Админ-панель" "admin.log"

Write-Host ""
Write-Host "=== Все сервисы перезапущены ===" -ForegroundColor Green
Write-Host ""
Write-Host "Сервисы доступны по адресам:" -ForegroundColor Cyan
Write-Host "  • Telegram бот: работает" -ForegroundColor White
Write-Host "  • API сервер: http://localhost:5050" -ForegroundColor White
Write-Host "  • API Swagger: http://localhost:5050/swagger/" -ForegroundColor White
Write-Host "  • Админ-панель: http://localhost:5051" -ForegroundColor White
Write-Host ""
Write-Host "Логи находятся в папке: logs\" -ForegroundColor Gray
Write-Host ""

# Проверка запущенных процессов
Write-Host "Проверка запущенных процессов:" -ForegroundColor Cyan
$running = Get-Process python -ErrorAction SilentlyContinue | Where-Object {
    try {
        $commandLine = (Get-CimInstance Win32_Process -Filter "ProcessId = $($_.Id)").CommandLine
        $commandLine -like "*app.bot.bot*" -or $commandLine -like "*app.api.api*" -or $commandLine -like "*app.admin.admin_panel*"
    } catch {
        $false
    }
}

if ($running) {
    Write-Host "  Найдено процессов: $($running.Count)" -ForegroundColor Green
    foreach ($proc in $running) {
        try {
            $cmd = (Get-CimInstance Win32_Process -Filter "ProcessId = $($proc.Id)").CommandLine
            if ($cmd) {
                $shortCmd = $cmd.Substring(0, [Math]::Min(100, $cmd.Length))
                Write-Host "    PID $($proc.Id): $shortCmd" -ForegroundColor Gray
            }
        } catch {
            Write-Host "    PID $($proc.Id)" -ForegroundColor Gray
        }
    }
} else {
    Write-Host "  Процессы не найдены. Возможно, они еще запускаются..." -ForegroundColor Yellow
}

Write-Host ""