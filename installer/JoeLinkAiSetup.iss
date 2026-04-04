; =============================================================================
; JoeLink AI - Inno Setup Installer Script
; File location: C:\Users\admin\joedocs\installer\joelinkai.iss
; =============================================================================

[Setup]
; --- App identity ---
AppName=JoeLink AI
AppVersion=1.0.0
AppVerName=JoeLink AI 1.0.0
AppPublisher=JoeCorp
AppPublisherURL=https://www.joelinkai.com
AppSupportURL=https://www.joelinkai.com/contact
AppUpdatesURL=https://www.joelinkai.com/download

; --- Install location ---
DefaultDirName={autopf}\JoeLinkAI
DefaultGroupName=JoeLink AI
; Allow the user to change the install directory
DisableDirPage=no

; --- Output ---
; The finished installer will be written to: installer\Output\JoeLinkAISetup.exe
OutputDir=Output
OutputBaseFilename=JoeLinkAISetup

; --- Installer appearance ---
; Custom icon for the installer itself (place joelinkai.ico in installer\ folder)
SetupIconFile=joelinkai.ico
; Wizard style: modern = nicer UI
WizardStyle=modern
; Show welcome page
DisableWelcomePage=no

; --- License ---
; Shows license.txt on a dedicated page during install
LicenseFile=C:\Users\admin\joedocs\license.txt

; --- Compression ---
Compression=lzma2/ultra64
SolidCompression=yes

; --- Uninstaller ---
UninstallDisplayName=JoeLink AI
UninstallDisplayIcon={app}\JoeLinkAI.exe

; --- Minimum Windows version (Windows 10) ---
MinVersion=10.0

; --- Misc ---
PrivilegesRequired=admin
ChangesAssociations=no


; =============================================================================
; LANGUAGES
; Supports English (default) and French.
; The installer will auto-detect the OS language and use it if available.
; =============================================================================
[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "french";  MessagesFile: "compiler:Languages\French.isl"


; =============================================================================
; TASKS
; Optional tasks shown on the "Select Additional Tasks" wizard page.
; =============================================================================
[Tasks]
; Optional desktop shortcut — user can uncheck this
Name: "desktopicon"; \
  Description: "{cm:CreateDesktopIcon}"; \
  GroupDescription: "{cm:AdditionalIcons}"; \
  Flags: unchecked


; =============================================================================
; FILES
; Copies JoeDocsClient.exe from dist\ and installs it as JoeLinkAI.exe
; =============================================================================
[Files]
; Main application executable — renamed to JoeLinkAI.exe on install
Source: "C:\Users\admin\joedocs\dist\JoeDocsClient.exe"; \
  DestDir: "{app}"; \
  DestName: "JoeLinkAI.exe"; \
  Flags: ignoreversion

; (Optional) Copy a readme file to the install directory
Source: "C:\Users\admin\joedocs\readme.txt"; \
  DestDir: "{app}"; \
  Flags: ignoreversion isreadme

; (Optional) Copy the icon so the uninstaller can use it
Source: "joelinkai.ico"; \
  DestDir: "{app}"; \
  Flags: ignoreversion


; =============================================================================
; ICONS (shortcuts)
; =============================================================================
[Icons]
; Start Menu shortcut
Name: "{group}\JoeLink AI"; \
  Filename: "{app}\JoeLinkAI.exe"; \
  IconFilename: "{app}\joelinkai.ico"; \
  Comment: "Launch JoeLink AI"

; Start Menu uninstall shortcut
Name: "{group}\Uninstall JoeLink AI"; \
  Filename: "{uninstallexe}"

; Desktop shortcut — only created if the user checked the task above
Name: "{autodesktop}\JoeLink AI"; \
  Filename: "{app}\JoeLinkAI.exe"; \
  IconFilename: "{app}\joelinkai.ico"; \
  Comment: "Launch JoeLink AI"; \
  Tasks: desktopicon


; =============================================================================
; RUN
; Optionally launch the app after install finishes.
; =============================================================================
[Run]
; Offer to launch JoeLink AI immediately after install
Filename: "{app}\JoeLinkAI.exe"; \
  Description: "{cm:LaunchProgram,JoeLink AI}"; \
  Flags: nowait postinstall skipifsilent


; =============================================================================
; UNINSTALL DELETE
; Clean up any files created at runtime that the uninstaller won't know about.
; Add entries here if your app writes config/log files to {app} or {userappdata}.
; =============================================================================
[UninstallDelete]
; Example: remove any log files left in the install folder
Type: filesandordirs; Name: "{app}\logs"
