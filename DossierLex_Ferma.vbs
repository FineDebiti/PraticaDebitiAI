' ==============================================================================
' DossierLex - Arresto Silenzioso dei Servizi Docker
' Studio Legale Avv. Aurelio Bentivegna
' ==============================================================================
Option Explicit
Dim WshShell, fso, scriptDir, cmdDocker

Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)

cmdDocker = "cmd.exe /c cd /d """ & scriptDir & """ && docker compose -f docker-compose.local.yml down"
WshShell.Run cmdDocker, 0, True

