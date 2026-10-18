#requires -Version 5.1
<#
.SYNOPSIS
    验证 PyInstaller 单文件 exe（dist\GameHub.exe）可正常启动。

.DESCRIPTION
    检查项：
      1. exe 存在及大小；
      2. PE Subsystem = 2（WINDOWS_GUI，运行时不会附带控制台窗口）；
      3. 启动后 WaitSeconds 秒内测试进程存在，且主窗口标题为「游戏脚本中心」；
      4. 只结束本次测试启动的 GameHub.exe 进程，绝不触碰已有 Hub 进程
         （pythonw.exe hub.pyw 或用户自行启动的 GameHub.exe）。

    程序的单实例互斥体（Local\GameHubLite_SingleInstance）若已被已有 Hub 占用，
    本脚本会以退出码 2 结束，提示先关闭已有实例再验证；脚本不会结束任何已有进程。

.PARAMETER Exe
    exe 路径，默认 <仓库根>\dist\GameHub.exe。

.PARAMETER WaitSeconds
    启动后等待并检查进程存活/窗口标题的秒数，默认 3。

.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File tools\verify_exe.ps1
    $LASTEXITCODE   # 0=通过，1=失败，2=被已有实例阻断

.NOTES
    task-5 打包验证脚本；不修改仓库、不 commit。
#>
[CmdletBinding()]
param(
    [string]$Exe = '',
    [int]$WaitSeconds = 3
)

$ErrorActionPreference = 'Stop'
$script:Failures = New-Object System.Collections.Generic.List[string]
$script:Checks = New-Object System.Collections.Generic.List[string]

function Add-Check([string]$Name, [bool]$Ok, [string]$Detail = '') {
    $label = if ($Ok) { 'PASS' } else { 'FAIL' }
    $line = "[$label] $Name"
    if ($Detail) { $line = "$line — $Detail" }
    $script:Checks.Add($line)
    if (-not $Ok) { $script:Failures.Add($Name) }
}

function Test-HubMutexHeld {
    # 程序用 CreateMutexW(None, False, "Local\GameHubLite_SingleInstance")；
    # .NET Mutex 未带前缀时同样位于本会话命名空间，可用 OpenExisting 探测。
    try {
        $m = [System.Threading.Mutex]::OpenExisting('GameHubLite_SingleInstance')
        try { return $true } finally { $m.Dispose() }
    }
    catch [System.Threading.WaitHandleCannotBeOpenedException] {
        return $false
    }
    catch {
        return $true   # 存在但无权限打开，仍视为已被占用
    }
}

function Get-PeSubsystem([string]$Path) {
    $fs = [System.IO.File]::Open($Path, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read)
    try {
        $buf = New-Object byte[] 4096
        $n = $fs.Read($buf, 0, $buf.Length)
        if ($n -lt 512) { throw 'PE 头部不足' }
        $eLfanew = [System.BitConverter]::ToInt32($buf, 0x3C)
        if ($eLfanew -le 0 -or ($eLfanew + 96) -gt $n) { throw 'e_lfanew 非法' }
        $magic = [System.BitConverter]::ToUInt16($buf, $eLfanew + 24)
        $subsystem = [System.BitConverter]::ToUInt16($buf, $eLfanew + 24 + 68)
        return [pscustomobject]@{ Magic = $magic; Subsystem = $subsystem }
    }
    finally { $fs.Dispose() }
}

# ---------------------------------------------------------------- 准备
$repoRoot = Split-Path -Parent $PSScriptRoot
if (-not $Exe) { $Exe = Join-Path $repoRoot 'dist\GameHub.exe' }
$title = '游戏脚本中心'

Write-Host "== GameHub exe 启动验证 =="
Write-Host "exe: $Exe"
Write-Host "等待: ${WaitSeconds}s"

if (-not (Test-Path -LiteralPath $Exe)) {
    Write-Host "FAIL: exe 不存在：$Exe" -ForegroundColor Red
    exit 1
}
$file = Get-Item -LiteralPath $Exe
$sizeMb = [math]::Round($file.Length / 1MB, 2)
Add-Check 'exe 存在且非空' ($file.Length -gt 0) ("{0:N0} 字节 / {1} MiB" -f $file.Length, $sizeMb)

$pe = Get-PeSubsystem -Path $Exe
Add-Check 'PE 为 64 位' ($pe.Magic -eq 0x20B) ("Magic=0x{0:X}" -f $pe.Magic)
Add-Check 'PE Subsystem=GUI（运行时无控制台窗口）' ($pe.Subsystem -eq 2) ("Subsystem={0}" -f $pe.Subsystem)

if (Test-HubMutexHeld) {
    Write-Host ''
    $script:Checks | ForEach-Object { Write-Host $_ }
    Write-Host ''
    Write-Host 'BLOCKED: 检测到已有 Hub 实例正在运行（单实例互斥体已被占用）。' -ForegroundColor Yellow
    Write-Host '         程序按设计不会启动第二个窗口；本脚本不会结束任何已有进程。'
    Write-Host '         请先关闭正在运行的 Hub，再重新运行本脚本。'
    exit 2
}

# ---------------------------------------------------------------- 启动与观察
$beforePids = @(Get-Process -Name 'GameHub' -ErrorAction SilentlyContinue |
                Select-Object -ExpandProperty Id)
$sw = [System.Diagnostics.Stopwatch]::StartNew()
$titleSeen = ''
$aliveWithinWait = $false
$testPids = @()
try {
    $started = Start-Process -FilePath $Exe -PassThru
    $deadline = $sw.Elapsed.Add([TimeSpan]::FromSeconds($WaitSeconds))
    while ($sw.Elapsed -lt $deadline) {
        $procs = @(Get-Process -Name 'GameHub' -ErrorAction SilentlyContinue |
                   Where-Object { $beforePids -notcontains $_.Id })
        if ($procs.Count -gt 0) {
            $aliveWithinWait = $true
            $testPids = @($procs | Select-Object -ExpandProperty Id)
            foreach ($p in $procs) {
                if ($p.MainWindowTitle -eq $title) { $titleSeen = $p.MainWindowTitle }
            }
            if ($titleSeen) { break }
        }
        Start-Sleep -Milliseconds 100
    }
    $elapsed = [math]::Round($sw.Elapsed.TotalSeconds, 2)
    $still = @(Get-Process -Name 'GameHub' -ErrorAction SilentlyContinue |
               Where-Object { $beforePids -notcontains $_.Id })
    if ($still.Count -gt 0) { $testPids = @($still | Select-Object -ExpandProperty Id) }

    Add-Check ("启动后 ${WaitSeconds}s 内测试进程存在") $aliveWithinWait ("首次出现于 {0}s" -f $elapsed)
    Add-Check '测试进程在观察期内持续存活' ($still.Count -gt 0) ("存活进程数: {0}" -f $still.Count)
    Add-Check "窗口标题为「$title」" ($titleSeen -eq $title) ("实际标题: '{0}'" -f $titleSeen)
    $withWin = @($still | Where-Object { $_.MainWindowHandle -ne 0 })
    Add-Check '存在可见主窗口' ($withWin.Count -gt 0) ("主窗口数: {0}" -f $withWin.Count)
}
finally {
    # 只清理本次测试启动的进程（按 PID，绝不按名称批量杀）
    foreach ($pid in @($testPids | Select-Object -Unique)) {
        if ($beforePids -notcontains $pid) {
            Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
        }
    }
}

# 已有 Hub 进程是否保持存活（只读检查，不结束）
foreach ($pid in $beforePids) {
    $still = Get-Process -Id $pid -ErrorAction SilentlyContinue
    Add-Check ("原有进程 PID $pid 未受影响") ($null -ne $still)
}

# ---------------------------------------------------------------- 汇总
Write-Host ''
$script:Checks | ForEach-Object { Write-Host $_ }
Write-Host ''
if ($script:Failures.Count -eq 0) {
    Write-Host 'RESULT: PASS — exe 可正常启动，窗口标题正确，无控制台窗口。' -ForegroundColor Green
    exit 0
}
Write-Host ('RESULT: FAIL — 失败项: ' + ($script:Failures -join '; ')) -ForegroundColor Red
exit 1
