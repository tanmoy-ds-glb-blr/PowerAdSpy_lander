@echo off
echo Creating virtual environment and installing requirements...
python -m venv venv
call venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
playwright install chromium
echo.
echo All requirements installed successfully!
pause
