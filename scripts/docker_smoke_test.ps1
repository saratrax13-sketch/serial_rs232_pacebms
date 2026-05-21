param(
    [string]$BaseUrl = "http://127.0.0.1:8099",
    [switch]$NoCache,
    [switch]$KeepRunning
)

$ErrorActionPreference = "Stop"

Write-Host "Pace BMS standalone Docker smoke test"
Write-Host "This validates Docker Compose config, image build, container startup, /health and /api/status."
Write-Host "If PACEBMS_SERIAL_DEVICE is set to /dev/null, this is startup/UI validation only."
Write-Host "It does not validate real BMS serial reads or Pace frame parsing without a real serial device."

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker was not found on PATH. Run this on a Docker host."
}

docker compose version
docker compose config

$buildArgs = @("compose", "build")
if ($NoCache) {
    $buildArgs += "--no-cache"
}
docker @buildArgs

docker compose up -d

try {
    $deadline = (Get-Date).AddSeconds(60)
    $health = $null
    $status = $null

    while ((Get-Date) -lt $deadline) {
        try {
            $health = Invoke-WebRequest -UseBasicParsing -Uri "$BaseUrl/health" -TimeoutSec 5
            $status = Invoke-WebRequest -UseBasicParsing -Uri "$BaseUrl/api/status" -TimeoutSec 5
            if ($health.StatusCode -in 200, 503 -and $status.StatusCode -eq 200) {
                break
            }
        } catch {
            Start-Sleep -Seconds 2
        }
    }

    if ($null -eq $health) {
        throw "No /health response received from $BaseUrl"
    }
    if ($null -eq $status -or $status.StatusCode -ne 200) {
        throw "No successful /api/status response received from $BaseUrl"
    }

    Write-Host "/health status: $($health.StatusCode)"
    Write-Host "/api/status status: $($status.StatusCode)"
    Write-Host "Container status:"
    docker compose ps
    Write-Host "Recent logs:"
    docker compose logs --tail=100 pacebms
    Write-Host "Docker smoke test passed."
}
finally {
    if (-not $KeepRunning) {
        docker compose down
    }
}
