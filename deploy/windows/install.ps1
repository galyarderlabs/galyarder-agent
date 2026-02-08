$ErrorActionPreference = "Stop"

function Write-Step([string]$Message) {
  Write-Host "[install] $Message" -ForegroundColor Cyan
}

function Write-WarnMsg([string]$Message) {
  Write-Host "[warn] $Message" -ForegroundColor Yellow
}

function Fail([string]$Message) {
  Write-Host "[error] $Message" -ForegroundColor Red
  exit 1
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

function Require-Command([string]$Name) {
  if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
    Fail "Missing required command: $Name"
  }
}

function Invoke-Python([string[]]$Args) {
  if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3 @Args
    return
  }
  if (Get-Command python -ErrorAction SilentlyContinue) {
    & python @Args
    return
  }
  Fail "Python not found. Install Python first."
}

$RepoUrl = Get-EnvOrDefault "G_AGENT_REPO_URL" "https://github.com/galyarderlabs/galyarder-agent.git"
$InstallDir = Get-EnvOrDefault "G_AGENT_INSTALL_DIR" (Join-Path $HOME "galyarder-agent")
$DataDir = Get-EnvOrDefault "G_AGENT_DATA_DIR" (Join-Path $HOME ".g-agent")
$SkipWinget = Get-BoolEnv "G_AGENT_SKIP_WINGET" $false
$SetupTasks = Get-BoolEnv "G_AGENT_SETUP_TASKS" $false

if ($PSVersionTable.PSVersion.Major -lt 5) {
  Fail "PowerShell 5+ is required."
}

if (-not $SkipWinget) {
  if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
    Write-WarnMsg "winget not found. Continue with G_AGENT_SKIP_WINGET=1 if dependencies already installed."
    Fail "winget is required for automatic dependency install."
  }

  Write-Step "Installing dependencies with winget..."
  $packages = @(
    "Git.Git",
    "Python.Python.3.12",
    "OpenJS.NodeJS.LTS"
  )

  foreach ($pkg in $packages) {
    & winget install --id $pkg --exact --source winget --accept-package-agreements --accept-source-agreements --silent
  }
}
else {
  Write-WarnMsg "Skipping winget dependency install (G_AGENT_SKIP_WINGET=1)."
}

Write-Step "Installing pipx (user scope)..."
Invoke-Python @("-m", "pip", "install", "--user", "--upgrade", "pip", "pipx")
Invoke-Python @("-m", "pipx", "ensurepath")

$pipxBin = Join-Path $HOME ".local\bin"
if (-not ($env:PATH -split ";" | Where-Object { $_ -eq $pipxBin })) {
  $env:PATH = "$pipxBin;$env:PATH"
}

Require-Command "git"
Require-Command "pipx"
Require-Command "npm"

if (Test-Path (Join-Path $InstallDir ".git")) {
  Write-Step "Updating existing repo at $InstallDir..."
  & git -C $InstallDir fetch origin main
  & git -C $InstallDir checkout main
  & git -C $InstallDir pull --ff-only
}
elseif (Test-Path $InstallDir) {
  Fail "Install dir exists but is not a git repo: $InstallDir"
}
else {
  Write-Step "Cloning repo to $InstallDir..."
  & git clone --depth=1 $RepoUrl $InstallDir
}

$pkgDir = Join-Path $InstallDir "backend\agent"
if (-not (Test-Path (Join-Path $pkgDir "pyproject.toml"))) {
  Fail "Backend package not found: $pkgDir"
}

Write-Step "Installing g-agent with pipx..."
& pipx install --force $pkgDir

$gAgentCmd = Get-Command "g-agent" -ErrorAction SilentlyContinue
$gAgentExe = if ($gAgentCmd) { $gAgentCmd.Source } else { Join-Path $pipxBin "g-agent.exe" }
if (-not (Test-Path $gAgentExe)) {
  Fail "g-agent executable not found after install."
}

$configPath = Join-Path $DataDir "config.json"
if (-not (Test-Path $configPath)) {
  Write-Step "Initializing fresh config/workspace at $DataDir..."
  $env:G_AGENT_DATA_DIR = $DataDir
  & $gAgentExe onboard
}
else {
  Write-Step "Config already exists at $configPath (keeping existing config)."
}

$bridgeSrc = Join-Path $InstallDir "backend\agent\bridge"
$bridgeDst = Join-Path $DataDir "bridge"
if (-not (Test-Path (Join-Path $bridgeSrc "package.json"))) {
  Fail "Bridge source missing: $bridgeSrc\package.json"
}

Write-Step "Setting up WhatsApp bridge at $bridgeDst..."
New-Item -ItemType Directory -Force -Path $DataDir | Out-Null
if (Test-Path $bridgeDst) {
  Remove-Item -Recurse -Force $bridgeDst
}
New-Item -ItemType Directory -Force -Path $bridgeDst | Out-Null
Copy-Item -Recurse -Force (Join-Path $bridgeSrc "*") $bridgeDst
Remove-Item -Recurse -Force (Join-Path $bridgeDst "node_modules"), (Join-Path $bridgeDst "dist") -ErrorAction SilentlyContinue

Push-Location $bridgeDst
& npm install
& npm run build
Pop-Location

if ($SetupTasks) {
  Write-Step "Creating startup tasks (schtasks)..."
  $gatewayCmd = "powershell -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -Command `"& '$gAgentExe' gateway`""
  $bridgeCmd = "powershell -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -Command `"& npm --prefix '$bridgeDst' start`""
  & schtasks /Create /F /SC ONLOGON /RL LIMITED /TN "g-agent-gateway" /TR $gatewayCmd | Out-Null
  & schtasks /Create /F /SC ONLOGON /RL LIMITED /TN "g-agent-wa-bridge" /TR $bridgeCmd | Out-Null
}
else {
  Write-WarnMsg "Skipping startup task creation. Set G_AGENT_SETUP_TASKS=1 to enable."
}

Write-Host ""
Write-Host "✅ g-agent install complete." -ForegroundColor Green
Write-Host ""
Write-Host "Paths:"
Write-Host "- Repo: $InstallDir"
Write-Host "- Data: $DataDir"
Write-Host ""
Write-Host "Next steps:"
Write-Host "1) Configure model/provider + allowlists:"
Write-Host "   notepad `"$configPath`""
Write-Host "2) Pair WhatsApp once (QR flow):"
Write-Host "   `$env:G_AGENT_DATA_DIR = `"$DataDir`"; g-agent channels login"
Write-Host "3) Check status:"
Write-Host "   `$env:G_AGENT_DATA_DIR = `"$DataDir`"; g-agent status"
Write-Host "   `$env:G_AGENT_DATA_DIR = `"$DataDir`"; g-agent doctor --network"
Write-Host "4) Run ops scripts:"
Write-Host "   $InstallDir\deploy\ops\healthcheck.sh   (via Git Bash/WSL)"
Write-Host "   $InstallDir\deploy\ops\backup.sh        (via Git Bash/WSL)"
