@echo off
if exist "%~dp0\.venv\Scripts\streamlit.exe" (
  "%~dp0\.venv\Scripts\streamlit.exe" %*
) else (
  echo Streamlit is not installed in the local virtual environment.
  echo Run "%~dp0\.venv\Scripts\python.exe -m pip install -r requirements.txt" first.
  exit /b 1
)
