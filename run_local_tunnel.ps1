# run_local_tunnel.ps1
$ErrorActionPreference = "Continue"

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "Starting Antigravity Server & Cloudflare Tunnel..." -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. 啟動 Flask 伺服器
Write-Host "[1/5] Starting Flask Server on port 5000..." -ForegroundColor Yellow
$server = Start-Process -FilePath "py" -ArgumentList "-3.12", "app.py" -PassThru -WindowStyle Hidden

Start-Sleep -Seconds 2

# 2. 啟動 Cloudflared
Write-Host "[2/5] Starting Cloudflare Tunnel..." -ForegroundColor Yellow
$cloudflaredPath = "C:\Program Files (x86)\cloudflared\cloudflared.exe"
$logFile = Join-Path $PSScriptRoot "cloudflared.log"
if (Test-Path $logFile) { Remove-Item $logFile -Force }

$tunnel = Start-Process -FilePath $cloudflaredPath -ArgumentList "tunnel", "--url", "http://localhost:5000", "--logfile", "`"$logFile`"" -PassThru -WindowStyle Hidden

# 3. 取得網址
Write-Host "[3/5] Waiting for public HTTPS tunnel URL..." -ForegroundColor Yellow
$tunnelUrl = $null
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 1
    if (Test-Path $logFile) {
        $raw = Get-Content $logFile -Raw -ErrorAction SilentlyContinue
        if ($raw -match "https://[-a-zA-Z0-9]+\.trycloudflare\.com") {
            $tunnelUrl = $matches[0]
            break
        }
    }
}

if (-not $tunnelUrl) {
    Write-Host "Failed to obtain tunnel URL." -ForegroundColor Red
    exit 1
}

Write-Host "Public URL obtained: $tunnelUrl" -ForegroundColor Green

# 4. 更新 gas_integration.js
Write-Host "[4/5] Updating gas_integration.js with tunnel URL..." -ForegroundColor Yellow
$gasFile = Join-Path $PSScriptRoot "gas_integration.js"
$gasContent = Get-Content $gasFile -Raw -Encoding UTF8
$targetLine = 'var BOT_SERVER_URL = "' + $tunnelUrl + '";'
$newContent = $gasContent -replace 'var BOT_SERVER_URL = ".*?";', $targetLine
Set-Content -Path $gasFile -Value $newContent -Encoding UTF8

# 5. 複製到剪貼簿並開啟試算表
Set-Clipboard -Value $newContent
Write-Host "Code copied to clipboard!" -ForegroundColor Green

Write-Host "[5/5] Opening https://sheets.new in default browser..." -ForegroundColor Yellow
Start-Process "https://sheets.new"

Write-Host "==========================================================" -ForegroundColor Green
Write-Host "SUCCESS! All backend components are running." -ForegroundColor Green
Write-Host "Tunnel URL: $tunnelUrl" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Green
