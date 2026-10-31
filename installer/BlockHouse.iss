#ifndef PayloadDir
  #error PayloadDir is required
#endif
#ifndef RuntimeInstaller
  #error RuntimeInstaller is required (offline Microsoft WebView2 x64 installer)
#endif
#ifndef AppRelease
  #define AppRelease "2.0.16"
#endif

[Setup]
AppId={{2BB0E7DA-D355-4676-BA39-D29486B9A250}
AppName=BlockHouse
AppVersion={#AppRelease}
DefaultDirName={localappdata}\Programs\BlockHouse
DefaultGroupName=BlockHouse
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=output
OutputBaseFilename=BlockHouse-Setup-{#AppRelease}-x64
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\BlockHouse.exe
AppMutex=Local\BlockHouseDesktop
CloseApplications=yes
RestartApplications=no
SetupLogging=yes
DisableProgramGroupPage=yes

[Tasks]
Name: "autostart"; Description: "Tự chạy BE khi đăng nhập Windows"
Name: "desktopicon"; Description: "Tạo biểu tượng BlockHouse trên Desktop"

[Files]
Source: "{#PayloadDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#RuntimeInstaller}"; DestDir: "{tmp}"; DestName: "WebView2Runtime.exe"; Flags: deleteafterinstall

[Icons]
Name: "{group}\BlockHouse"; Filename: "{app}\BlockHouse.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\BlockHouse"; Filename: "{app}\BlockHouse.exe"; WorkingDir: "{app}"; Tasks: desktopicon
Name: "{group}\Chạy BE"; Filename: "{app}\BlockHouse.exe"; Parameters: "--backend"; WorkingDir: "{app}"
Name: "{group}\Dừng BE để bảo trì"; Filename: "{app}\BlockHouse.exe"; Parameters: "--stop-backend"; WorkingDir: "{app}"
Name: "{group}\Dữ liệu và backup"; Filename: "{localappdata}\BlockHouse\data"

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "BlockHouseBackend"; ValueData: """{app}\BlockHouse.exe"" --backend"; Flags: uninsdeletevalue; Tasks: autostart
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueName: "BlockHouseBackend"; Flags: deletevalue; Check: not WizardIsTaskSelected('autostart')

[Run]
Filename: "{tmp}\WebView2Runtime.exe"; Parameters: "/silent /install"; StatusMsg: "Đang chuẩn bị WebView2 Runtime offline…"; Flags: waituntilterminated runhidden
Filename: "{app}\BlockHouse.exe"; Parameters: "--backend"; Flags: nowait runhidden
Filename: "{app}\BlockHouse.exe"; Description: "Mở BlockHouse"; Flags: postinstall nowait skipifsilent

[Code]
var
  ImportPage: TInputFileWizardPage;
  WebsitePage: TInputQueryWizardPage;

function DataFolder: String;
begin
  Result := ExpandConstant('{localappdata}\BlockHouse\data');
end;

procedure InitializeWizard;
begin
  ImportPage := CreateInputFilePage(wpSelectDir, 'Dữ liệu BlockHouse',
    'Chọn database cũ nếu muốn tiếp tục dùng dữ liệu hiện có.',
    'Bỏ trống để tạo database mới. Không tự nhập dữ liệu mẫu. Database gốc được giữ nguyên; bộ cài không ghi đè database đã có.');
  ImportPage.Add('Database cũ (.db):', 'SQLite database|*.db;*.sqlite3|All files|*.*', '.db');
  WebsitePage := CreateInputQueryPage(ImportPage.ID, 'Website BlockHouse',
    'Cho phép website kết nối BE trên máy này.',
    'Nhập domain HTTPS chính thức, ví dụ https://blockhouse.example.com. Có thể bỏ trống để dùng Desktop và web local http://127.0.0.1:8080; chỉnh domain sau trong backend-config.json.');
  WebsitePage.Add('Website HTTPS (không có đường dẫn):', False);
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := ((PageID = ImportPage.ID) and FileExists(DataFolder + '\BlockHouse.db')) or
    ((PageID = WebsitePage.ID) and FileExists(DataFolder + '\backend-config.json'));
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var
  Url, Host: String;
  I: Integer;
begin
  Result := True;
  if (CurPageID = ImportPage.ID) and (ImportPage.Values[0] <> '') and not FileExists(ImportPage.Values[0]) then begin
    MsgBox('Không tìm thấy database đã chọn.', mbError, MB_OK); Result := False;
  end;
  if CurPageID = WebsitePage.ID then begin
    Url := Trim(WebsitePage.Values[0]);
    if Url = '' then exit;
    if Pos('https://', Url) <> 1 then begin
      MsgBox('Website phải dùng HTTPS.', mbError, MB_OK); Result := False; exit;
    end;
    Host := Copy(Url, 9, Length(Url));
    if (Length(Host) = 0) or (Pos('.', Host) = 0) then Result := False;
    for I := 1 to Length(Host) do
      if not (((Host[I] >= 'a') and (Host[I] <= 'z')) or ((Host[I] >= 'A') and (Host[I] <= 'Z')) or ((Host[I] >= '0') and (Host[I] <= '9')) or (Host[I] = '.') or (Host[I] = '-')) then Result := False;
    if not Result then MsgBox('Chỉ nhập domain HTTPS, không có dấu / cuối, cổng hoặc đường dẫn.', mbError, MB_OK);
  end;
end;

function StopInstalledBackend: Boolean;
var
  ExitCode: Integer;
begin
  Result := True;
  if FileExists(ExpandConstant('{app}\BlockHouse.exe')) then
    Result := Exec(ExpandConstant('{app}\BlockHouse.exe'), '--stop-backend', ExpandConstant('{app}'), SW_HIDE, ewWaitUntilTerminated, ExitCode) and (ExitCode = 0);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  Result := '';
  if not StopInstalledBackend then Result := 'Không dừng được BE. Hoàn tất đơn đang nhập, đóng BlockHouse và dừng BE trước khi cài lại.';
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  Settings, Url, Source: String;
  ExitCode: Integer;
begin
  if CurStep <> ssPostInstall then exit;
  ForceDirectories(DataFolder);
  if not FileExists(DataFolder + '\backend-config.json') then begin
    Url := Trim(WebsitePage.Values[0]);
    Settings := '{"allowed_origins":[';
    if Url <> '' then Settings := Settings + '"' + Url + '"';
    Settings := Settings + '],"allowed_hosts":[],"backup":{"interval_hours":6,"keep":30}}';
    if not SaveStringToFile(DataFolder + '\backend-config.json', Settings, False) then
      RaiseException('Không lưu được cấu hình BE.');
  end;
  Source := ImportPage.Values[0];
  if (Source <> '') and not FileExists(DataFolder + '\BlockHouse.db') then
    if not Exec(ExpandConstant('{app}\BE.exe'), '--data-dir "' + DataFolder + '" --import-db "' + Source + '"', DataFolder, SW_HIDE, ewWaitUntilTerminated, ExitCode) or (ExitCode <> 0) then
      RaiseException('Không nhập được database. File gốc vẫn được giữ nguyên. Kiểm tra log và chạy lại bộ cài.');
end;

function InitializeUninstall: Boolean;
begin
  Result := MsgBox('Đóng BlockHouse và hoàn tất thanh toán trước khi gỡ. Dữ liệu, backup và cấu hình tại AppData sẽ được giữ lại. Tiếp tục?', mbConfirmation, MB_YESNO) = IDYES;
  if Result then Result := StopInstalledBackend;
end;
