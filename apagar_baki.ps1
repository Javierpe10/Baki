# Apaga BAKI: detiene el backend (y con él las rutinas programadas).
# Lo usa el acceso directo «Apagar BAKI» del escritorio.
$procesos = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*uvicorn app.main:app*" }
foreach ($p in $procesos) { Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue }

Add-Type -AssemblyName PresentationFramework
if ($procesos) {
    [System.Windows.MessageBox]::Show("BAKI se ha apagado.", "BAKI", "OK", "Information") | Out-Null
} else {
    [System.Windows.MessageBox]::Show("BAKI no estaba encendido.", "BAKI", "OK", "Information") | Out-Null
}
