@echo off
@REM set /p "PORT=Enter Android WiFi Port number: "
@REM set ANDROID_SERIAL=192.168.178.102:%PORT%

@REM adb connect %ANDROID_SERIAL%
@REM adb shell "mkdir -p /storage/E42C-0EA8/Music/___Playlists"
@REM adb pull "/storage/E42C-0EA8/Music/___Playlists" M:\Music

"P:\musify\.venv\Scripts\python.exe" "P:\musify\main.py" -cfg main
"P:\musify\.venv\Scripts\python.exe" "P:\musify\main.py" -cfg update_tags
echo Metadata sync complete. Update playlists now, then press any key to sync playlists with Spotify
pause
"P:\musify\.venv\Scripts\python.exe" "P:\musify\main.py" -cfg update_spotify

@REM adb shell "rm -rf /storage/E42C-0EA8/Music/___Playlists"
@REM adb push D:\Music\___Playlists "/storage/E42C-0EA8/Music"
@REM rmdir /s /q "D:\Music\___Playlists"
