#!/bin/bash

# Flaskアプリ起動（バックグラウンド）
python3 /home/monokai/Desktop/video_preload_app/app.py &

# 少し待機してからブラウザ起動
sleep 3

# Chromiumをフルスクリーン(kiosk)で起動
chromium-browser --kiosk http://localhost:8080
