@echo off
REM ============================================================
REM  DevNexAI - Construye el ejecutable de la app de escritorio
REM  Genera dist\DevNexAI.exe  (ventana moderna, sin consola)
REM ============================================================

echo [1/2] Instalando dependencias de build...
py -m pip install pyinstaller rich customtkinter pillow

echo.
echo [2/2] Construyendo DevNexAI.exe (modo ventana)...
py -m PyInstaller --onefile --windowed --name DevNexAI ^
  --icon devnexai.ico ^
  --collect-all rich --collect-all customtkinter ^
  --hidden-import devnexai.gui --hidden-import devnexai.ui ^
  --hidden-import devnexai.agent --hidden-import devnexai.providers ^
  --hidden-import devnexai.config --hidden-import devnexai.memory ^
  --hidden-import devnexai.safety --hidden-import devnexai.tools ^
  devnexai_gui.py --clean -y

echo.
echo ============================================================
echo  Listo. Ejecutable de la app:  dist\DevNexAI.exe
echo ============================================================
echo  Para crear el INSTALADOR: instala Inno Setup y abre installer.iss
echo ============================================================
pause
