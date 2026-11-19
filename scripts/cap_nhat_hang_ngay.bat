@echo off
rem Cập nhật dữ liệu SSI tự động (dùng cho Task Scheduler). Tự tìm thư mục repo từ vị trí file này.
cd /d "%~dp0.."
if not exist logs mkdir logs
set PYTHONUTF8=1
".venv\Scripts\python.exe" scripts\update_data.py >> logs\cap_nhat_hang_ngay.txt 2>&1
