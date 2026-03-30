@echo off
echo Building HL7 Anonymizer...
pyinstaller --onefile --windowed --name "HL7_Anonymizer" src/main.py
echo Done.
pause
