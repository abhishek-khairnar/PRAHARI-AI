<#
.SYNOPSIS
    PRAHARI-AI Multi-Camera Intelligent Surveillance Platform PowerShell Launcher
.DESCRIPTION
    Launches PRAHARI-AI 4-camera real-time surveillance server and automatically opens
    the command center web interface at http://localhost:8001.
#>

$ErrorActionPreference = "Continue"

Write-Host "==============================================================================" -ForegroundColor Cyan
Write-Host " PRAHARI-AI — Multi-Camera AI Surveillance Command Center" -ForegroundColor Yellow
Write-Host "==============================================================================" -ForegroundColor Cyan

# Set project root to script directory
Set-Location -Path $PSScriptRoot
$projectRoot = Get-Location
Write-Host "[*] Project Root: $projectRoot" -ForegroundColor Gray

# Check Python
try {
    $pyVersion = python --version 2>&1
    Write-Host "[*] Python Environment: $pyVersion" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Python was not found in PATH. Please ensure Python is installed and accessible." -ForegroundColor Red
    exit 1
}

# Check GPU CUDA
try {
    $gpuStatus = python -c "import torch; print(f'CUDA GPU ({torch.cuda.get_device_name(0)})' if torch.cuda.is_available() else 'CPU Fallback')" 2>&1
    Write-Host "[*] AI Acceleration: $gpuStatus" -ForegroundColor Green
} catch {
    Write-Host "[!] Could not probe PyTorch CUDA device." -ForegroundColor Yellow
}

# Check Video Sources
Write-Host "[*] Validating Multi-Camera Video Streams..." -ForegroundColor Gray
$demoVideos = @(
    @{ Id = "CAM-01"; Path = "demo_videos\border_demo.mp4" },
    @{ Id = "CAM-02"; Path = "demo_videos\night_demo.mp4" },
    @{ Id = "CAM-03"; Path = "demo_videos\activity-demo.mp4"; Alt = "demo_videos\activity_demo.mp4" },
    @{ Id = "CAM-04"; Path = "demo_videos\cctv_demo.mp4" }
)

foreach ($vid in $demoVideos) {
    if (Test-Path $vid.Path) {
        Write-Host "    [+] $($vid.Id): $($vid.Path) [READY]" -ForegroundColor Green
    } elseif ($vid.Alt -and (Test-Path $vid.Alt)) {
        Write-Host "    [+] $($vid.Id): $($vid.Alt) [READY]" -ForegroundColor Green
    } else {
        Write-Host "    [!] $($vid.Id): File not found at $($vid.Path)" -ForegroundColor Yellow
    }
}

Write-Host "`n==============================================================================" -ForegroundColor Cyan
Write-Host " Starting Server on http://localhost:8001 (Press Ctrl+C to stop)" -ForegroundColor Yellow
Write-Host "==============================================================================`n" -ForegroundColor Cyan

# Open browser after 3 seconds in background job
Start-Job -ScriptBlock {
    Start-Sleep -Seconds 3
    Start-Process "http://localhost:8001"
} | Out-Null

# Execute main server
python main.py
