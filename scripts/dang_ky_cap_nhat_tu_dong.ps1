# Đăng ký tác vụ Windows tự cập nhật dữ liệu SSI lúc 15:30 các ngày thứ Hai - thứ Sáu.
# Máy tắt đúng giờ đó thì tác vụ tự chạy bù ngay khi máy bật lại (StartWhenAvailable).
#
# Cách chạy (PowerShell, trong thư mục gốc repo):
#     powershell -ExecutionPolicy Bypass -File scripts\dang_ky_cap_nhat_tu_dong.ps1
# Gỡ bỏ:
#     Unregister-ScheduledTask -TaskName "VonOn cap nhat du lieu" -Confirm:$false

$bat = Join-Path $PSScriptRoot "cap_nhat_hang_ngay.bat"
$action = New-ScheduledTaskAction -Execute $bat
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday, Tuesday, Wednesday, Thursday, Friday -At 3:30PM
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 30)
Register-ScheduledTask -TaskName "VonOn cap nhat du lieu" -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
Write-Host "Da dang ky tac vu 'VonOn cap nhat du lieu': 15:30 thu Hai - thu Sau. Nhat ky: logs\cap_nhat_hang_ngay.txt"
