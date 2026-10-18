# -*- coding: utf-8 -*-
"""在桌面创建「游戏脚本中心」快捷方式（源码运行 / 打包 exe 运行都支持）。"""
$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot          # 仓库根目录
$exe = Join-Path $root 'GameHub.exe'

if (Test-Path $exe) {
    $target = $exe
    $arguments = ''
} else {
    $candidates = @(
        (Get-Command pythonw.exe -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source),
        (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python313\pythonw.exe'),
        (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\pythonw.exe'),
        (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python311\pythonw.exe'),
        (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python310\pythonw.exe'),
        (Join-Path $env:ProgramFiles 'Python313\pythonw.exe')
    ) | Where-Object { $_ -and (Test-Path $_) }

    if (-not $candidates) {
        Write-Host '[错误] 没有找到 Python，请先安装 Python 3 并勾选 Add python.exe to PATH。'
        exit 1
    }
    $target = @($candidates)[0]
    $arguments = '"' + (Join-Path $root 'hub.pyw') + '"'
}

$desktop = [Environment]::GetFolderPath('Desktop')
$lnkPath = Join-Path $desktop '游戏脚本中心.lnk'
$ws = New-Object -ComObject WScript.Shell
$lnk = $ws.CreateShortcut($lnkPath)
$lnk.TargetPath = $target
$lnk.Arguments = $arguments
$lnk.WorkingDirectory = $root
$lnk.IconLocation = (Join-Path $root 'assets\hub.ico') + ',0'
$lnk.Description = '游戏脚本中心 · 一键启动游戏脚本'
$lnk.Save()
Write-Host "已创建桌面快捷方式：$lnkPath"
