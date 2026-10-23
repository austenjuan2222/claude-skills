$ErrorActionPreference = 'Stop'
$homeDir = Join-Path $env:USERPROFILE '.claude\skills-updater'
$skillsDir = Join-Path $env:USERPROFILE '.claude\skills'
$repoDir = Join-Path $homeDir 'repository'
$backupDir = Join-Path $homeDir ('backups\installer-' + (Get-Date -Format yyyyMMddHHmmss))
New-Item -ItemType Directory -Path $homeDir -Force | Out-Null
foreach ($name in @('skill_updater.py','update-skills.ps1','config.json','sources.json','README.md')) {
    $existing = Join-Path $homeDir $name
    if (Test-Path -LiteralPath $existing) {
        New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
        Copy-Item -LiteralPath $existing -Destination (Join-Path $backupDir $name)
    }
}
foreach ($name in @('skill_updater.py','update-skills.ps1','sources.json','README.md')) {
    $source = Join-Path $PSScriptRoot $name
    $target = Join-Path $homeDir $name
    if ([IO.Path]::GetFullPath($source) -ne [IO.Path]::GetFullPath($target)) { Copy-Item -LiteralPath $source -Destination $target -Force }
}
$python = (Get-Command python.exe -ErrorAction Stop).Source
$npm = (Get-Command npm.cmd -ErrorAction Stop).Source
$sources = Get-Content -LiteralPath (Join-Path $homeDir 'sources.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$config = @{ skills=$skillsDir; repository=$repoDir; python=$python; npm=$npm; sources=$sources }
$config | ConvertTo-Json -Depth 40 | Set-Content -LiteralPath (Join-Path $homeDir 'config.json') -Encoding utf8
if (-not (Test-Path -LiteralPath (Join-Path $repoDir '.git'))) {
    if (Test-Path -LiteralPath $repoDir) { throw 'Repository destination exists without .git; inspect it before cloning.' }
    & git clone --depth 1 'https://github.com/austenjuan2222/claude-skills.git' $repoDir
    if ($LASTEXITCODE -ne 0) { throw 'Could not clone the private source repository. Sign in to GitHub and retry.' }
}
Write-Output "Claude updater installed at $homeDir. Installed skills were not overwritten."
