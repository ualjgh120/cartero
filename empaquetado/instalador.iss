; Instalador de Windows (Inno Setup, gratuito). Lo lanza GitHub Actions:
;   iscc /DNombre=Cartero /DVersion=0.1.0 empaquetado\instalador.iss
#ifndef Nombre
  #define Nombre "Cartero"
#endif
#ifndef Version
  #define Version "0.1.0"
#endif

[Setup]
; identificador propio de Cartero (no cambiarlo: Windows lo usa para actualizar y desinstalar)
AppId={{1A0581BD-68BE-4CE9-8B1E-5A0C78384849}
AppName={#Nombre}
AppVersion={#Version}
AppPublisher={#Nombre}
DefaultDirName={autopf}\{#Nombre}
DefaultGroupName={#Nombre}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=..\dist
OutputBaseFilename={#Nombre}-{#Version}-Windows-instalador
SetupIconFile=..\recursos\icono.ico
UninstallDisplayIcon={app}\{#Nombre}.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "es"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "escritorio"; Description: "Crear un acceso directo en el escritorio"; GroupDescription: "Accesos directos:"

[Files]
Source: "..\dist\{#Nombre}\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\{#Nombre}"; Filename: "{app}\{#Nombre}.exe"
Name: "{autodesktop}\{#Nombre}"; Filename: "{app}\{#Nombre}.exe"; Tasks: escritorio

[Run]
Filename: "{app}\{#Nombre}.exe"; Description: "Abrir {#Nombre}"; Flags: nowait postinstall skipifsilent
