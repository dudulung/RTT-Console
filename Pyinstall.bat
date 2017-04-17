@echo off
cls
echo *************************************
:: 
pyinstaller -w --onefile --path "C:\Program Files\Python35\Lib\site-packages\PyQt5\Qt\bin" --icon="Ui\icons\pander.ico" --noupx main.py

echo done!

pause

