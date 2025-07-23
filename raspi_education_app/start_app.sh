#!/bin/bash

# Flaskアプリ起動（バックグラウンド）
python3 /home/monokai/Desktop/git/raspi_education_app/app.py &

# 少し待機してからブラウザ起動
sleep 3

# Chromiumをフルスクリーン(kiosk)で起動
firefox --kiosk http://localhost:8080
