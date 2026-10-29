' ==============================================================================
' DossierLex - Avvio Silenzioso in Modalita' Desktop App (Zero Finestre Nere)
' Studio Legale Avv. Aurelio Bentivegna
' ==============================================================================
Option Explicit
Dim WshShell, fso, scriptDir, cmdDocker, edgePath, urlApp

Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

' Cartella del progetto
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)

' 1. Avvia i container Docker in background 100% invisibile (parametro 0 = hidden)
cmdDocker = "cmd.exe /c cd /d """ & scriptDir & """ && docker compose -f docker-compose.local.yml up -d"
WshShell.Run cmdDocker, 0, True

' 2. Attendi 2 secondi per verificare la prontezza del frontend
WScript.Sleep 2000

' 3. Rileva il browser Microsoft Edge (o Google Chrome come alternativa)
edgePath = ""
If fso.FileExists("C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe") Then
    edgePath = "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
ElseIf fso.FileExists("C:\Program Files\Microsoft\Edge\Application\msedge.exe") Then
    edgePath = "C:\Program Files\Microsoft\Edge\Application\msedge.exe"
ElseIf fso.FileExists("C:\Program Files\Google\Chrome\Application\chrome.exe") Then
    edgePath = "C:\Program Files\Google\Chrome\Application\chrome.exe"
ElseIf fso.FileExists("C:\Program Files (x86)\Google\Chrome\Application\chrome.exe") Then
    edgePath = "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
End If

' 4. Apri DossierLex in Finestra Dedicata Desktop App (senza barre del browser)
urlApp = "http://localhost:3001"
If edgePath <> "" Then
    WshShell.Run """" & edgePath & """ --app=" & urlApp, 1, False
Else
    WshShell.Run urlApp, 1, False
End If

