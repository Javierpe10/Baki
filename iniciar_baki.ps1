# Arranca BAKI: backend en 127.0.0.1:8001 (sirve también la interfaz) y abre la ventana en Edge.
# Lo usa el acceso directo «BAKI» del escritorio. También se puede lanzar a mano:
#   powershell -ExecutionPolicy Bypass -File <carpeta BAKI>\iniciar_baki.ps1
# -Compilar fuerza recompilar la interfaz (se recompila sola si el código es más nuevo).
param([switch]$Compilar)

$ErrorActionPreference = "Stop"
$raiz = $PSScriptRoot
$python = Join-Path $raiz ".venv\Scripts\python.exe"
$backend = Join-Path $raiz "backend"
$frontend = Join-Path $raiz "frontend"
$dist = Join-Path $frontend "dist\index.html"
$logs = Join-Path $backend "data"
$url = "http://127.0.0.1:8001"

function Avisar($texto) {
    Add-Type -AssemblyName PresentationFramework
    [System.Windows.MessageBox]::Show($texto, "BAKI", "OK", "Warning") | Out-Null
}

function EnLinea {
    try { Invoke-RestMethod "$url/health" -TimeoutSec 2 | Out-Null; return $true } catch { return $false }
}

try {
    # 1. Recompilar la interfaz si falta o si el código es más reciente.
    $recompilar = $Compilar -or -not (Test-Path $dist)
    if (-not $recompilar) {
        $compilada = (Get-Item $dist).LastWriteTime
        $cambios = Get-ChildItem (Join-Path $frontend "src") -Recurse -File | Where-Object { $_.LastWriteTime -gt $compilada }
        $recompilar = [bool]$cambios
    }
    if ($recompilar) {
        Push-Location $frontend
        if (-not (Test-Path "node_modules")) { npm install --silent | Out-Null }
        npm run build --silent | Out-Null
        Pop-Location
    }

    # 2. n8n vive en Docker (contenedor con reinicio automático): basta con que Docker esté encendido.
    $docker = "$env:ProgramFiles\Docker\Docker\Docker Desktop.exe"
    if ((Test-Path $docker) -and -not (Get-Process "Docker Desktop" -ErrorAction SilentlyContinue)) {
        Start-Process $docker -WindowStyle Minimized
    }

    # 3. Backend: si no responde, cerrar restos colgados y arrancarlo oculto.
    if (-not (EnLinea)) {
        Get-CimInstance Win32_Process |
            Where-Object { $_.CommandLine -like "*uvicorn app.main:app*" } |
            ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }

        New-Item -ItemType Directory -Force -Path $logs | Out-Null
        Start-Process -FilePath $python `
            -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8001" `
            -WorkingDirectory $backend -WindowStyle Hidden `
            -RedirectStandardOutput (Join-Path $logs "baki_salida.log") `
            -RedirectStandardError (Join-Path $logs "baki_errores.log")

        $listo = $false
        for ($i = 0; $i -lt 40; $i++) {
            Start-Sleep -Milliseconds 500
            if (EnLinea) { $listo = $true; break }
        }
        if (-not $listo) {
            Avisar "BAKI no ha podido arrancar. Revisa el archivo:`n$logs\baki_errores.log"
            exit 1
        }
    }

    # 4. Ventana de BAKI en Edge (voces naturales en español y micrófono).
    $edge = "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe"
    if (-not (Test-Path $edge)) { $edge = "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe" }
    if (Test-Path $edge) {
        Start-Process $edge "--app=$url"
    } else {
        Start-Process $url
    }
} catch {
    Avisar "Error al iniciar BAKI:`n$($_.Exception.Message)"
    exit 1
}
