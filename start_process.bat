@echo off
cd /d "%~dp0"
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
) else (
    if exist myenv_lander\Scripts\activate.bat (
        call myenv_lander\Scripts\activate.bat
    )
)
python new_lander.py
