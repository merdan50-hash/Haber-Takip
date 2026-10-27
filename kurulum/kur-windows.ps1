# Haber Takip — Windows kurulum aracı.
# Hizmeti kurar, oturum açılışında arka planda otomatik başlatır ve eklentiyi erişim anahtarıyla hazırlar.
# Yeniden çalıştırmak güvenlidir; kayıtlar ve anahtar korunur. Sonraki sürümler GitHub'dan kendiliğinden kurulur.
param([switch]$Sessiz)

$ErrorActionPreference = "Stop"
try { [Console]::OutputEncoding = [Text.Encoding]::UTF8 } catch { }

$VarsayilanPort = 18765
$Paket = Split-Path -Parent $MyInvocation.MyCommand.Path
$HizmetDir = Join-Path $env:LOCALAPPDATA "HaberTakip"
$EklentiDir = Join-Path $env:USERPROFILE "HaberTakip\eklenti"
$Gorev = "HaberTakip Hizmeti"
$Log = Join-Path $HizmetDir "hizmet.log"
$Utf8 = New-Object Text.UTF8Encoding $false

function Hata([string]$Mesaj) { Write-Host ""; Write-Host "HATA: $Mesaj" -ForegroundColor Red; exit 1 }
function Adim([string]$Mesaj) { Write-Host "• $Mesaj" -ForegroundColor Cyan }

if (-not (Test-Path (Join-Path $Paket "hizmet\haber_takip_hizmeti.py")) -or -not (Test-Path (Join-Path $Paket "eklenti\manifest.json"))) {
  Hata "Kurulum dosyaları eksik. Zip dosyasını tamamen açıp (Tümünü ayıkla) kur-windows.bat dosyasını klasörün içinden çalıştırın."
}

function Python-Bul {
  # Microsoft Store'un "python" kısayolu gerçek Python değildir; gerçekten çalışanı ara.
  $adaylar = @()
  if (Get-Command py -ErrorAction SilentlyContinue) { $adaylar += ,@("py", "-3") }
  foreach ($ad in "python", "python3") { if (Get-Command $ad -ErrorAction SilentlyContinue) { $adaylar += ,@($ad) } }
  Get-ChildItem (Join-Path $env:LOCALAPPDATA "Programs\Python\Python3*\python.exe") -ErrorAction SilentlyContinue |
    Sort-Object FullName -Descending | ForEach-Object { $adaylar += ,@($_.FullName) }
  foreach ($aday in $adaylar) {
    try {
      $komut = $aday[0]; $ekler = @($aday | Select-Object -Skip 1)
      $yol = & $komut @ekler -c "import sys; assert sys.version_info >= (3, 8); print(sys.executable)" 2>$null
      if ($LASTEXITCODE -eq 0 -and $yol -and (Test-Path $yol.Trim())) { return $yol.Trim() }
    } catch { }
  }
  return $null
}

Adim "Python 3 denetleniyor"
$Python = Python-Bul
if (-not $Python) {
  if (Get-Command winget -ErrorAction SilentlyContinue) {
    Adim "Python yükleniyor (winget, yalnızca bu kullanıcı için)"
    winget install --exact --id Python.Python.3.12 --scope user --silent --accept-package-agreements --accept-source-agreements | Out-Host
    $Python = Python-Bul
  }
  if (-not $Python) {
    Hata "Python 3 bulunamadı. https://www.python.org/downloads/ adresinden yükleyip bu aracı yeniden çalıştırın."
  }
}
$Pythonw = Join-Path (Split-Path -Parent $Python) "pythonw.exe"
if (-not (Test-Path $Pythonw)) { $Pythonw = $Python }

Adim "Eski hizmet durduruluyor (varsa)"
Stop-ScheduledTask -TaskName $Gorev -ErrorAction SilentlyContinue
Get-CimInstance Win32_Process -Filter "Name LIKE 'python%'" -ErrorAction SilentlyContinue |
  Where-Object { $_.CommandLine -like "*haber_takip_hizmeti.py*" } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
function Dolu([int]$No) { [bool](Get-NetTCPConnection -LocalPort $No -State Listen -ErrorAction SilentlyContinue) }
$PortDosyasi = Join-Path $HizmetDir "port"
$Tercih = $VarsayilanPort
if (Test-Path $PortDosyasi) { $Tercih = [int]((Get-Content $PortDosyasi -Raw).Trim()) }
for ($i = 0; $i -lt 10 -and (Dolu $Tercih); $i++) { Start-Sleep -Milliseconds 500 }

# Bağlantı noktası başka bir programdaysa onu bozmadan boş bir bağlantı noktasına geç.
$Port = $null
foreach ($Aday in @($Tercih) + (($VarsayilanPort..18799) | Where-Object { $_ -ne $Tercih })) {
  if (Dolu $Aday) {
    $Sahip = Get-NetTCPConnection -LocalPort $Aday -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1 |
      ForEach-Object { (Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue).Path }
    Write-Host "  $Aday numaralı bağlantı noktası dolu ($Sahip); başka bir numara deneniyor."
  } else { $Port = $Aday; break }
}
if (-not $Port) { Hata "18765–18799 arasında boş bağlantı noktası bulunamadı." }

Adim "Hizmet kuruluyor: $HizmetDir"
New-Item -ItemType Directory -Force -Path $HizmetDir | Out-Null
[IO.File]::WriteAllText($PortDosyasi, "$Port", $Utf8)
Copy-Item (Join-Path $Paket "hizmet\haber_takip_hizmeti.py") $HizmetDir -Force
$TokenDosyasi = Join-Path $HizmetDir "token"
if (-not (Test-Path $TokenDosyasi) -or -not (Get-Content $TokenDosyasi -Raw).Trim()) {
  $Token = (& $Python -c "import secrets; print(secrets.token_urlsafe(32))").Trim()
  [IO.File]::WriteAllText($TokenDosyasi, $Token, $Utf8)
}
$Token = (Get-Content $TokenDosyasi -Raw).Trim()

Adim "Eklenti hazırlanıyor: $EklentiDir"
New-Item -ItemType Directory -Force -Path $EklentiDir | Out-Null
Get-ChildItem $EklentiDir -Force | Remove-Item -Recurse -Force
Copy-Item (Join-Path $Paket "eklenti\*") $EklentiDir -Recurse -Force
Get-ChildItem $EklentiDir -Recurse -File | Unblock-File -ErrorAction SilentlyContinue
$Ayar = @{ url = "http://127.0.0.1:$Port"; token = $Token } | ConvertTo-Json -Compress
[IO.File]::WriteAllText((Join-Path $EklentiDir "bridge-config.js"),
  "// Kurulum aracı bu dosyaya yalnız bu kuruluma ait bağlantıyı yazar.`nglobalThis.HABER_BRIDGE = $Ayar;`n", $Utf8)

Adim "Otomatik başlatma ayarlanıyor"
function Tirnak([string]$Deger) { '"' + $Deger + '"' }
$Argumanlar = @(
  (Tirnak (Join-Path $HizmetDir "haber_takip_hizmeti.py")),
  "--data", (Tirnak $HizmetDir), "--port", $Port, "--log", (Tirnak $Log), "--extension-dir", (Tirnak $EklentiDir)
) -join " "
$Baslatma = "Görev Zamanlayıcı ($Gorev)"
try {
  $Kullanici = [Security.Principal.WindowsIdentity]::GetCurrent().Name
  $Eylem = New-ScheduledTaskAction -Execute $Pythonw -Argument $Argumanlar -WorkingDirectory $HizmetDir
  $Tetik = New-ScheduledTaskTrigger -AtLogOn -User $Kullanici
  $Ayarlar = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
    -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -MultipleInstances IgnoreNew
  $Kimlik = New-ScheduledTaskPrincipal -UserId $Kullanici -LogonType Interactive -RunLevel Limited
  Register-ScheduledTask -TaskName $Gorev -Action $Eylem -Trigger $Tetik -Settings $Ayarlar -Principal $Kimlik -Force | Out-Null
  Start-ScheduledTask -TaskName $Gorev
} catch {
  # Görev oluşturulamazsa (ör. kurum ilkesi) Başlangıç klasörüne kısayol koy.
  $Kisayol = Join-Path ([Environment]::GetFolderPath("Startup")) "Haber Takip Hizmeti.lnk"
  $Kabuk = New-Object -ComObject WScript.Shell
  $Lnk = $Kabuk.CreateShortcut($Kisayol)
  $Lnk.TargetPath = $Pythonw; $Lnk.Arguments = $Argumanlar; $Lnk.WorkingDirectory = $HizmetDir; $Lnk.WindowStyle = 7
  $Lnk.Save()
  Start-Process -FilePath $Pythonw -ArgumentList $Argumanlar -WorkingDirectory $HizmetDir -WindowStyle Hidden
  $Baslatma = "Başlangıç klasörü kısayolu"
}

Adim "Hizmetin açılması bekleniyor"
$Hazir = $false
for ($i = 0; $i -lt 40; $i++) {
  try {
    Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/status" -Headers @{ Authorization = "Bearer $Token" } -TimeoutSec 2 | Out-Null
    $Hazir = $true; break
  } catch { Start-Sleep -Milliseconds 500 }
}
if (-not $Hazir) { Hata "Hizmet yanıt vermedi. Ayrıntı: $Log" }

Write-Host ""
Write-Host "Hizmet çalışıyor (http://127.0.0.1:$Port). Otomatik başlatma: $Baslatma" -ForegroundColor Green
Write-Host @"

Son adım — eklentiyi tarayıcıya ekleyin (yalnızca ilk kurulumda gerekir).
Chrome, Edge, Brave, Opera ve Vivaldi desteklenir:
  1. Adres çubuğuna  chrome://extensions  yazın (Edge: edge://extensions).
  2. "Geliştirici modu"nu açın.
  3. "Paketlenmemiş öğe yükle"ye basın ve şu klasörü seçin:
       $EklentiDir
  4. Araç çubuğundaki yapboz simgesinden Haber Takip'i sabitleyip tıklayın.

Yeni sürümler GitHub'dan kendiliğinden kurulur; eklenti de kendini yeniler.
"@
if (-not $Sessiz) {
  try { Set-Clipboard -Value $EklentiDir; Write-Host "(Klasör yolu panoya kopyalandı.)" } catch { }
  Start-Process explorer.exe (Split-Path -Parent $EklentiDir)
}
