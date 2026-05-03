; Trucking Pay Wizard — Inno Setup installer script
;
; Produces: dist\TruckingPayWizardSetup.exe
;
; Requirements:
;   - Inno Setup 6.x with ISPP (Inno Setup Pre-Processor) support.
;     Download: https://jrsoftware.org/isdl.php
;   - PyInstaller one-folder bundle must exist at: dist\TruckingPayWizard\
;
; Build with:
;   iscc packaging\installer.iss
;
; Or use packaging\build.ps1 which runs both steps in sequence.

#define MyAppName      "Trucking Pay Wizard"
#define MyAppPublisher "bernardo-heberle"
#define MyAppExeName   "TruckingPayWizard.exe"
#define MyDistDir      "..\dist\TruckingPayWizard"

; Read version from __version__.py at build time.
; ISPP exec: extract the version string with a small Python snippet.
#define MyAppVersion   GetStringFileInfo("..\dist\TruckingPayWizard\TruckingPayWizard.exe", "FileVersion")
; Fallback if GetStringFileInfo returns empty (no version resource):
#if MyAppVersion == ""
  #define MyAppVersion "0.1.0"
#endif

; ---------------------------------------------------------------------------
; [Setup]
; ---------------------------------------------------------------------------
[Setup]
; Stable GUID — DO NOT change this after the first release.
; Inno Setup uses it to recognise upgrades vs fresh installs.
AppId={{0467D9FD-C633-4F29-B7AB-E101FAE85B83}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL=https://github.com/bernardo-heberle/trucking-pay-wizard-releases
AppSupportURL=https://github.com/bernardo-heberle/trucking-pay-wizard-releases/issues
AppUpdatesURL=https://github.com/bernardo-heberle/trucking-pay-wizard-releases/releases

; Per-user install — no admin rights required.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=commandline

; Install into the user's Program Files folder.
DefaultDirName={userpf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
DisableDirPage=no

; Allow silent upgrades to close and restart the app.
CloseApplications=yes
RestartApplications=yes

; Output
OutputDir=..\dist
OutputBaseFilename=TruckingPayWizardSetup
Compression=lzma2/max
SolidCompression=yes

; Appearance
WizardStyle=modern
WizardResizable=yes

; Uninstall
Uninstallable=yes
UninstallDisplayName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}

; ---------------------------------------------------------------------------
; [Languages]
; ---------------------------------------------------------------------------
[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

; ---------------------------------------------------------------------------
; [Tasks]
; ---------------------------------------------------------------------------
[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

; ---------------------------------------------------------------------------
; [Files]
; ---------------------------------------------------------------------------
[Files]
; Bundle the entire PyInstaller one-folder output.
Source: "{#MyDistDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

; ---------------------------------------------------------------------------
; [Icons]
; ---------------------------------------------------------------------------
[Icons]
; Start Menu
Name: "{group}\{#MyAppName}";         Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
; Desktop (optional, off by default above)
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

; ---------------------------------------------------------------------------
; [Run]
; ---------------------------------------------------------------------------
[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

; ---------------------------------------------------------------------------
; [UninstallDelete]
; Remove the app-data folder (logs, update state) on uninstall.
; Does NOT remove Windows Credential Manager entries — those survive reinstall
; so users don't have to re-enter their keys after an upgrade.
; ---------------------------------------------------------------------------
[UninstallDelete]
Type: filesandordirs; Name: "{localappdata}\TruckingPayWizard"
