$ErrorActionPreference = "Stop"

function Write-Step([string]$Message) {
  Write-Host "[uninstall] $Message" -ForegroundColor Cyan
}

function Write-WarnMsg([string]$Message) {
  Write-Host "[warn] $Message" -ForegroundColor Yellow
}

function Get-EnvOrDefault([string]$Name, [string]$Default) {
  $value = [Environment]::GetEnvironmentVariable($Name)
  if ($value -and $value.Trim() -ne "") {
    return $value
  }
  return $Default
}

function Get-BoolEnv([string]$Name, [bool]$Default = $false) {
  $value = [Environment]::GetEnvironmentVariable($Name)
  if (-not $value) { return $Default }
  return @("1", "true", "yes", "on") -contains $value.ToLowerInvariant()
}

$InstallDir = Get-EnvOrDefault "G_AGENT_INSTALL_DIR" (Join-Path $HOME "galyarder-agent")
$DataDir = Get-EnvOrDefault "G_AGENT_DATA_DIR" (Join-Path $HOME ".g-agent")
$RemoveServices = Get-BoolEnv "G_AGENT_REMOVE_SERVICES" $true
$RemoveRepo = Get-BoolEnv "G_AGENT_REMOVE_REPO" $false
$WipeData = Get-BoolEnv "G_AGENT_WIPE_DATA" $false

if ($RemoveServices) {
  Write-Step "Removing startup tasks (if present)..."
  & schtasks /Delete /TN "g-agent-gateway" /F | Out-Null 2>$null
  & schtasks /Delete /TN "g-agent-wa-bridge" /F | Out-Null 2>$null
}
else {
  Write-WarnMsg "Skipping startup task removal (G_AGENT_REMOVE_SERVICES=0)."
}

if (Get-Command pipx -ErrorAction SilentlyContinue) {
  Write-Step "Removing pipx package..."
  & pipx uninstall galyarder-agent | Out-Null 2>$null
  & pipx uninstall g-agent | Out-Null 2>$null
}
else {
  Write-WarnMsg "pipx not found; skipping pipx uninstall."
}

Remove-Item -Force -ErrorAction SilentlyContinue (Join-Path $HOME ".local\bin\g-agent.exe")
Remove-Item -Force -ErrorAction SilentlyContinue (Join-Path $HOME ".local\bin\g-agent")

if (Test-Path $DataDir) {
  if ($WipeData) {
    Write-Step "Removing full data dir: $DataDir"
    Remove-Item -Recurse -Force $DataDir
  }
  else {
    Write-Step "Keeping memory/config data. Removing runtime bridge artifacts only."
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue (Join-Path $DataDir "bridge")
    Remove-Item -Force -ErrorAction SilentlyContinue `
      (Join-Path $DataDir "gateway.log"), `
      (Join-Path $DataDir "gateway.err.log"), `
      (Join-Path $DataDir "wa-bridge.log"), `
      (Join-Path $DataDir "wa-bridge.err.log")
  }
}
else {
  Write-WarnMsg "Data dir not found: $DataDir"
}

if ($RemoveRepo) {
  if (Test-Path $InstallDir) {
    Write-Step "Removing repo dir: $InstallDir"
    Remove-Item -Recurse -Force $InstallDir
  }
  else {
    Write-WarnMsg "Repo dir not found: $InstallDir"
  }
}
else {
  Write-WarnMsg "Keeping repo dir (set G_AGENT_REMOVE_REPO=1 to remove): $InstallDir"
}

Write-Host ""
Write-Host "✅ g-agent uninstall flow complete." -ForegroundColor Green
Write-Host ""
Write-Host "Kept by default:"
Write-Host "- $DataDir\config.json"
Write-Host "- $DataDir\workspace\memory"
Write-Host "- $DataDir\cron"
Write-Host "- repo directory: $InstallDir"
Write-Host ""
Write-Host "To fully wipe everything:"
Write-Host "  `$env:G_AGENT_WIPE_DATA='1'; `$env:G_AGENT_REMOVE_REPO='1'; .\deploy\windows\uninstall.ps1"
