# Haber Takip — Windows kaldırma aracı.
param([switch]$Sil)
try { [Console]::OutputEncoding = [Text.Encoding]::UTF8 } catch { }

$HizmetDir = Join-Path $env:LOCALAPPDATA "HaberTakip"
$Gorev = "HaberTakip Hizmeti"

Stop-ScheduledTask -TaskName $Gorev -ErrorAction SilentlyContinue
Unregister-ScheduledTask -TaskName $Gorev -Confirm:$false -ErrorAction SilentlyContinue
Remove-Item (Join-Path ([Environment]::GetFolderPath("Startup")) "Haber Takip Hizmeti.lnk") -Force -ErrorAction SilentlyContinue
Get-CimInstance Win32_Process -Filter "Name LIKE 'python%'" -ErrorAction SilentlyContinue |
  Where-Object { $_.CommandLine -like "*haber_takip_hizmeti.py*" } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Write-Host "Hizmet durduruldu ve otomatik başlatma kaldırıldı."

if (-not $Sil) { $Sil = (Read-Host "Kaynak listesi ve haber kayıtları da silinsin mi? [e/H]") -match "^[eE]" }
if ($Sil) {
  Start-Sleep -Seconds 1
  Remove-Item $HizmetDir, (Join-Path $env:USERPROFILE "HaberTakip") -Recurse -Force -ErrorAction SilentlyContinue
  Write-Host "Kayıtlar ve eklenti klasörü silindi."
} else {
  Remove-Item (Join-Path $HizmetDir "haber_takip_hizmeti.py") -Force -ErrorAction SilentlyContinue
  Write-Host "Kayıtlar korundu: $HizmetDir"
}
Write-Host "Son olarak tarayıcının eklentiler sayfasından Haber Takip eklentisini kaldırın."
