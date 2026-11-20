# Install Desktop Goose from source on Windows and start it at every login.
# Run in PowerShell:  powershell -ExecutionPolicy Bypass -File install.ps1
$ErrorActionPreference = "Stop"
$dir = $PSScriptRoot
Set-Location $dir
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "Python 3 is required: https://www.python.org/downloads/"
}
python -m venv venv
& "$dir\venv\Scripts\python.exe" -m pip install --quiet --upgrade pip -r requirements.txt

$startup = [Environment]::GetFolderPath("Startup")
$sh = New-Object -ComObject WScript.Shell
$lnk = $sh.CreateShortcut("$startup\Desktop Goose.lnk")
$lnk.TargetPath = "$dir\venv\Scripts\pythonw.exe"
$lnk.Arguments = "`"$dir\goose.py`""
$lnk.WorkingDirectory = $dir
$lnk.Save()

Start-Process "$dir\venv\Scripts\pythonw.exe" -ArgumentList "`"$dir\goose.py`""
Write-Host "Goose installed and will start at login. Remove '$startup\Desktop Goose.lnk' to uninstall."
