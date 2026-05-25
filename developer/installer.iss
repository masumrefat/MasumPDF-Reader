; ============================================================
;  MasumPDF Reader - Windows Installer (Inno Setup script)
;  Created by Chowdhury Mohammad Masum Refat (MIT License)
;
;  This builds a single setup.exe that:
;    - shows normal installer pages (welcome, license, folder, etc.)
;    - installs the app into Program Files
;    - installs Python automatically if it is missing
;    - installs all Python dependencies during setup
;    - creates Start Menu and Desktop shortcuts with the app icon
;    - registers the app in "Apps & features" (Add/Remove Programs)
;
;  HOW TO BUILD (one time, on a Windows PC):
;    1. Install Inno Setup (free): https://jrsoftware.org/isdl.php
;    2. Put python-3.12.4-amd64.exe next to this file (download from
;       https://www.python.org/downloads/) so it can be bundled.
;    3. Open this .iss file in Inno Setup and click Build > Compile.
;    4. The finished installer appears in the "Output" folder as
;       "MasumPDF-Reader-Setup.exe".
; ============================================================

#define MyAppName "MasumPDF Reader"
#define MyAppVersion "1.0.2"
#define MyAppPublisher "Chowdhury Mohammad Masum Refat"
#define MyAppExeName "pythonw.exe"

[Setup]
; This .iss lives in the "developer" folder, but the app files (LICENSE,
; resources, main.py, etc.) are one level UP, in the main folder. SourceDir
; tells Inno Setup to look there for all the source files below.
SourceDir=..
OutputDir=developer\Output
AppId={{B7E2B1A4-6C3D-4F2A-9E1D-MASUMPDF2026}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\MasumPDF Reader
DefaultGroupName=MasumPDF Reader
DisableProgramGroupPage=yes
LicenseFile=LICENSE
; The icon shown for the installer itself and in Add/Remove Programs:
SetupIconFile=resources\icons\app.ico
UninstallDisplayIcon={app}\resources\icons\app.ico
OutputBaseFilename=MasumPDF-Reader-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"
Name: "associatepdf"; Description: "Make MasumPDF Reader available as a PDF opener"; GroupDescription: "File associations:"

[Registry]
; Register the app so Windows lists it under "Open with" and lets the user
; set it as the default PDF reader (Settings > Default apps).
Root: HKCR; Subkey: "MasumPDFReader.Document"; ValueType: string; ValueData: "PDF Document"; Flags: uninsdeletekey; Tasks: associatepdf
Root: HKCR; Subkey: "MasumPDFReader.Document\DefaultIcon"; ValueType: string; ValueData: "{app}\resources\icons\app.ico"; Tasks: associatepdf
Root: HKCR; Subkey: "MasumPDFReader.Document\shell\open\command"; ValueType: string; ValueData: """{app}\.venv\Scripts\pythonw.exe"" ""{app}\main.py"" ""%1"""; Tasks: associatepdf
; Add to the "Open with" list for .pdf files
Root: HKCR; Subkey: ".pdf\OpenWithProgids"; ValueType: string; ValueName: "MasumPDFReader.Document"; ValueData: ""; Flags: uninsdeletevalue; Tasks: associatepdf
; Register under RegisteredApplications so it appears in Default Apps
Root: HKLM; Subkey: "SOFTWARE\MasumPDFReader\Capabilities"; ValueType: string; ValueName: "ApplicationName"; ValueData: "MasumPDF Reader"; Tasks: associatepdf
Root: HKLM; Subkey: "SOFTWARE\MasumPDFReader\Capabilities"; ValueType: string; ValueName: "ApplicationDescription"; ValueData: "Read, edit and compare PDF files"; Tasks: associatepdf
Root: HKLM; Subkey: "SOFTWARE\MasumPDFReader\Capabilities\FileAssociations"; ValueType: string; ValueName: ".pdf"; ValueData: "MasumPDFReader.Document"; Tasks: associatepdf
Root: HKLM; Subkey: "SOFTWARE\RegisteredApplications"; ValueType: string; ValueName: "MasumPDF Reader"; ValueData: "SOFTWARE\MasumPDFReader\Capabilities"; Flags: uninsdeletevalue; Tasks: associatepdf

[Files]
; The whole application folder. Exclude dev files, python installers, zips.
Source: "*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs; Excludes: ".venv\*,__pycache__\*,*.pyc,developer\*,python-*.exe,python-bundled.exe,*.zip,SETUP.bat,INSTALL.bat,UNINSTALL.bat,SETUP_MAC.command,HOW_TO_INSTALL.txt,.gitignore"
; Bundle the Python installer IF it is present next to the app. The
; "skipifsourcedoesntexist" flag means the build still works when it's absent
; (in that case Python is downloaded from the web during install instead).
Source: "python-3.12.4-amd64.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall skipifsourcedoesntexist; Check: NeedsPython

[Run]
; 1a) If Python is missing AND we bundled the installer, run the bundled one.
Filename: "{tmp}\python-3.12.4-amd64.exe"; Parameters: "/quiet InstallAllUsers=1 PrependPath=1 Include_launcher=1"; StatusMsg: "Installing Python..."; Check: NeedsPython and BundledPythonExists; Flags: waituntilterminated
; 1b) If Python is missing and NOT bundled, download it from python.org first.
Filename: "powershell"; Parameters: "-NoProfile -Command ""Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.12.4/python-3.12.4-amd64.exe' -OutFile '{tmp}\pydl.exe' -UseBasicParsing"""; StatusMsg: "Downloading Python..."; Check: NeedsPython and (not BundledPythonExists); Flags: waituntilterminated runhidden
Filename: "{tmp}\pydl.exe"; Parameters: "/quiet InstallAllUsers=1 PrependPath=1 Include_launcher=1"; StatusMsg: "Installing Python..."; Check: NeedsPython and (not BundledPythonExists); Flags: waituntilterminated

; 2) Create the app's virtual environment.
;    Use our helper that locates python.exe even right after installing it
;    (when "py" may not yet be on PATH in this same session).
Filename: "{code:GetPythonPath}"; Parameters: "-m venv ""{app}\.venv"""; StatusMsg: "Creating environment..."; Flags: runhidden waituntilterminated

; 3) Install all required Python packages into that environment.
Filename: "{app}\.venv\Scripts\python.exe"; Parameters: "-m pip install --upgrade pip"; StatusMsg: "Updating pip..."; Flags: runhidden waituntilterminated
Filename: "{app}\.venv\Scripts\python.exe"; Parameters: "-m pip install -r ""{app}\requirements.txt"""; StatusMsg: "Installing components (this can take a few minutes)..."; Flags: runhidden waituntilterminated

; 4) Offer to launch the app at the end.
Filename: "{app}\.venv\Scripts\pythonw.exe"; Parameters: """{app}\main.py"""; Description: "Launch MasumPDF Reader"; Flags: nowait postinstall skipifsilent

[Icons]
; Start Menu shortcut
Name: "{group}\MasumPDF Reader"; Filename: "{app}\.venv\Scripts\pythonw.exe"; Parameters: """{app}\main.py"""; WorkingDir: "{app}"; IconFilename: "{app}\resources\icons\app.ico"
; Uninstall entry in Start Menu
Name: "{group}\Uninstall MasumPDF Reader"; Filename: "{uninstallexe}"
; Optional desktop shortcut (controlled by the task above)
Name: "{autodesktop}\MasumPDF Reader"; Filename: "{app}\.venv\Scripts\pythonw.exe"; Parameters: """{app}\main.py"""; WorkingDir: "{app}"; IconFilename: "{app}\resources\icons\app.ico"; Tasks: desktopicon

[UninstallDelete]
; Remove the environment we created so uninstall leaves nothing behind.
Type: filesandordirs; Name: "{app}\.venv"
Type: filesandordirs; Name: "{app}\__pycache__"

[Code]
{ True if we bundled a Python installer in the tmp folder. }
function BundledPythonExists(): Boolean;
begin
  Result := FileExists(ExpandConstant('{tmp}\python-3.12.4-amd64.exe'));
end;

{ Find a usable python.exe, checking common install locations. This works
  even right after Python was installed in this same setup run, when "py"
  may not be on PATH yet. }
function GetPythonPath(Param: String): String;
var
  Candidates: array of String;
  i: Integer;
begin
  Result := 'py';  { default fallback }
  SetArrayLength(Candidates, 8);
  Candidates[0] := ExpandConstant('{commonpf}\Python312\python.exe');
  Candidates[1] := ExpandConstant('{commonpf}\Python311\python.exe');
  Candidates[2] := ExpandConstant('{commonpf}\Python313\python.exe');
  Candidates[3] := ExpandConstant('{commonpf}\Python310\python.exe');
  Candidates[4] := ExpandConstant('{localappdata}\Programs\Python\Python312\python.exe');
  Candidates[5] := ExpandConstant('{localappdata}\Programs\Python\Python311\python.exe');
  Candidates[6] := ExpandConstant('{localappdata}\Programs\Python\Python313\python.exe');
  Candidates[7] := ExpandConstant('{localappdata}\Programs\Python\Python310\python.exe');
  for i := 0 to GetArrayLength(Candidates) - 1 do
  begin
    if FileExists(Candidates[i]) then
    begin
      Result := Candidates[i];
      Exit;
    end;
  end;
end;

{ Returns True if Python is NOT already installed (so setup should install it). }
function NeedsPython(): Boolean;
var
  ResultCode: Integer;
begin
  { Try running "py --version". If it fails, Python launcher is missing. }
  if Exec('py', '--version', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) and (ResultCode = 0) then
  begin
    Result := False;  { Python is present }
  end
  else
  begin
    Result := True;   { Python is missing -> install it }
  end;
end;
