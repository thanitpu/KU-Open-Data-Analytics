param(
  [Parameter(Mandatory=$true)][string]$RegistrationToken,
  [string]$RepositoryUrl = 'https://github.com/thanitpu/KU-Open-Data-Analytics',
  [string]$InstallDir = 'C:\ku2d-actions-runner',
  [string]$RunnerName = "$env:COMPUTERNAME-ku2d-acquisition",
  [string]$Labels = 'ku2d-acquisition,thailand,windows'
)

$ErrorActionPreference = 'Stop'

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
  throw 'Run this setup from an elevated PowerShell window (Run as Administrator).'
}

New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
Set-Location $InstallDir

$release = Invoke-RestMethod -Headers @{ 'User-Agent'='KU2D-Edge-Runner-Setup' } -Uri 'https://api.github.com/repos/actions/runner/releases/latest'
$asset = $release.assets | Where-Object { $_.name -match '^actions-runner-win-x64-.*\.zip$' } | Select-Object -First 1
if (-not $asset) { throw 'Unable to locate the official Windows x64 GitHub Actions runner asset.' }

$zip = Join-Path $InstallDir $asset.name
if (-not (Test-Path $zip)) {
  Write-Host "Downloading official GitHub Actions runner $($release.tag_name)..."
  Invoke-WebRequest -Headers @{ 'User-Agent'='KU2D-Edge-Runner-Setup' } -Uri $asset.browser_download_url -OutFile $zip
}

if (-not (Test-Path (Join-Path $InstallDir 'config.cmd'))) {
  Expand-Archive -Path $zip -DestinationPath $InstallDir -Force
}

Write-Host 'Configuring KU2D Edge Runner...'
& .\config.cmd --unattended --replace --url $RepositoryUrl --token $RegistrationToken --name $RunnerName --labels $Labels --work '_work'
if ($LASTEXITCODE -ne 0) { throw "GitHub runner configuration failed with exit code $LASTEXITCODE." }

Write-Host 'Installing runner as a Windows service...'
& .\svc.cmd install
if ($LASTEXITCODE -ne 0) { throw "Runner service installation failed with exit code $LASTEXITCODE." }
& .\svc.cmd start
if ($LASTEXITCODE -ne 0) { throw "Runner service start failed with exit code $LASTEXITCODE." }

Write-Host ''
Write-Host 'KU2D Edge Runner setup completed.'
Write-Host "Runner name : $RunnerName"
Write-Host "Labels      : $Labels"
Write-Host "Repository  : $RepositoryUrl"
Write-Host 'Next: confirm the runner is Idle under GitHub Settings > Actions > Runners.'
