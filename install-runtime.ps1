$ErrorActionPreference = 'Stop'
$applicationRoot = 'D:\Applications\GPTResearcher'
$cacheRoot = 'D:\Caches\GPTResearcher'
$receiptRoot = 'D:\Artifacts\GPTResearcher\installation'
$bootstrapPython = 'C:\Users\fy\AppData\Local\Python\pythoncore-3.14-64\python.exe'
New-Item -ItemType Directory -Path $applicationRoot,$cacheRoot,$receiptRoot,(Join-Path $cacheRoot 'tmp') -Force | Out-Null
$env:PIP_CACHE_DIR = Join-Path $cacheRoot 'pip'
$env:npm_config_cache = Join-Path $cacheRoot 'npm'
$env:TEMP = Join-Path $cacheRoot 'tmp'
$env:TMP = $env:TEMP
$venv = Join-Path $applicationRoot 'venv'
if (-not (Test-Path -LiteralPath $venv)) {
    & $bootstrapPython -m venv $venv
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
$python = Join-Path $venv 'Scripts\python.exe'
& $python -m pip install --upgrade pip --disable-pip-version-check
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $python -m pip install --require-virtualenv --disable-pip-version-check --progress-bar off --log (Join-Path $receiptRoot 'pip-install.log') --report (Join-Path $receiptRoot 'pip-install.json') 'gpt-researcher==0.16.1' 'fastmcp>=2.8,<3' ddgs
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$sdkCheckout = 'D:\Quarantine\GPTResearcherVerification\sign-in-with-chatgpt-devkit'
Push-Location -LiteralPath $sdkCheckout
try {
    npm.cmd pack --workspace '@siwc/local' --pack-destination $cacheRoot
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} finally { Pop-Location }
$sdkRuntime = Join-Path $applicationRoot 'siwc'
New-Item -ItemType Directory -Path $sdkRuntime -Force | Out-Null
npm.cmd install --prefix $sdkRuntime --omit=dev --ignore-scripts --no-audit --no-fund (Join-Path $cacheRoot 'siwc-local-0.1.0.tgz')
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $python -m pip check
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $python -c "import importlib.metadata as m; print({p:m.version(p) for p in ['gpt-researcher','fastmcp','langchain-openai','ddgs']})"
exit $LASTEXITCODE
