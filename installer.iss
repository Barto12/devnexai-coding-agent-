; ============================================================
;  DevNexAI - Script de instalador (Inno Setup)
;  Requiere: Inno Setup  ->  https://jrsoftware.org/isdl.php
;
;  PASOS:
;   1. Ejecuta primero build_exe.bat para generar dist\DevNexAI.exe
;   2. Instala Inno Setup
;   3. Abre este archivo (installer.iss) con Inno Setup
;   4. Pulsa "Compile" (o Build > Compile)
;   5. Se genera  Output\DevNexAI-Setup.exe  -> ese es el instalador
;      que el usuario ejecuta. Crea acceso directo en el escritorio
;      y en el menu inicio, con icono.
; ============================================================

#define MyAppName "DevNexAI"
#define MyAppVersion "0.3.0"
#define MyAppPublisher "DevNexAI"
#define MyAppExeName "DevNexAI.exe"

[Setup]
AppId={{B7E3A1C2-9F4D-4E8A-A1B2-DEVNEXAI0001}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
; El instalador se llamara DevNexAI-Setup.exe
OutputBaseFilename=DevNexAI-Setup
OutputDir=Output
Compression=lzma
SolidCompression=yes
WizardStyle=modern
SetupIconFile=devnexai.ico
; No requiere admin si se instala en carpeta del usuario:
PrivilegesRequiredOverridesAllowed=dialog

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "Crear un acceso directo en el escritorio"; GroupDescription: "Accesos directos:"; Flags: checkedonce

[Files]
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "README.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
; Menu inicio
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
; Escritorio (segun la tarea marcada)
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
; Ofrecer abrir la app al terminar la instalacion
Filename: "{app}\{#MyAppExeName}"; Description: "Ejecutar {#MyAppName}"; Flags: nowait postinstall skipifsilent
