from flask import Flask, render_template, request, jsonify
from werkzeug.utils import secure_filename
import os
import json
import shutil

# --- GPIOの取り扱い ---
try:
    import RPi.GPIO as GPIO
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    GPIO.setup(17, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    GPIO.setup(27, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    GPIO_AVAILABLE = True
except (ImportError, RuntimeError):
    print("GPIO not available - using dummy mode.")
    GPIO_AVAILABLE = False

    class DummyGPIO:
        def input(self, pin): return 0
    GPIO = DummyGPIO()

# --- Flask アプリケーション ---
app = Flask(__name__)
MANUAL_DIR = os.path.join(app.root_path, "static", "manuals")
INDEX_FILE = os.path.join(app.root_path, "data", "manual_index.json")
os.makedirs(MANUAL_DIR, exist_ok=True)
os.makedirs(os.path.dirname(INDEX_FILE), exist_ok=True)

# --- 日本語フォルダ名用の安全変換関数 ---
def sanitize_foldername(name):
    invalid = '\\/:*?"<>|'
    for c in invalid:
        name = name.replace(c, '-')
    return name.strip() or "manual"

# --- 動画手順書登録 ---
@app.route("/register_manual", methods=["GET", "POST"])
def register_manual():
    if request.method == "GET":
        return render_template("register_manual.html")
    else:
        print("=== DEBUG: request.form ===", request.form)
        print("=== DEBUG: request.files ===", request.files)

        title = request.form.get("title", "").strip()
        if not title:
            return "手順書名が空です", 400

        folder_name = sanitize_foldername(title)
        if not folder_name:
            return "無効な手順書名です", 400

        manual_path = os.path.join(MANUAL_DIR, folder_name)
        os.makedirs(manual_path, exist_ok=True)

        files = request.files.getlist("videos")
        if not files:
            return "動画ファイルがありません", 400

        for i, f in enumerate(files):
            f.save(os.path.join(manual_path, f"{i+1}.mp4"))

        manuals = []
        if os.path.exists(INDEX_FILE):
            with open(INDEX_FILE, "r", encoding="utf-8") as f:
                manuals = json.load(f)
        manuals = [m for m in manuals if m["title"] != title]
        manuals.append({ "title": title, "path": f"manuals/{folder_name}" })
        with open(INDEX_FILE, "w", encoding="utf-8") as f:
            json.dump(manuals, f, ensure_ascii=False, indent=2)

        return ("", 204)

# --- GPIO状態返却 ---
@app.route("/gpio_status")
def gpio_status():
    return jsonify({
        "gpio17": GPIO.input(17) if GPIO_AVAILABLE else 0,
        "gpio27": GPIO.input(27) if GPIO_AVAILABLE else 0
    })

# --- 各種ルート ---
@app.route("/")
def menu():
    return render_template("index.html")

@app.route("/video")
def video_mode():
    return render_template("video_player.html")

@app.route("/video_menu")
def video_menu():
    return render_template("video_menu.html")

@app.route("/video_manual_selector")
def video_manualselector():
    return render_template("video_manual_selector.html")

@app.route("/video_player")
def video_player():
    return render_template("video_player.html")

@app.route("/video_container")
def video_container():
    title = request.args.get("title", "")
    return render_template("video_container.html", title=title)

@app.route("/video_inner_player")
def video_inner_player():
    title = request.args.get("title", "")
    return render_template("video_inner_player.html", title=title)

@app.route("/timer")
def timer_mode():
    return render_template("timer_mode.html")

@app.route("/manual_list")
def manual_list():
    return render_template("manual_list.html")
    
@app.route("/edit_manual")
def edit_manual():
    return render_template("edit_manual.html")
    
@app.route("/get_manual")
def get_manual():
    title = request.args.get("title", "")
    folder_name = sanitize_foldername(title)
    manual_path = os.path.join(MANUAL_DIR, folder_name)
    if not os.path.exists(manual_path):
        return "指定された手順書が見つかりません", 404

    files = []
    for i in range(1, 100):  # 最大100ステップまでチェック（必要に応じて拡張）
        file_path = os.path.join(manual_path, f"{i}.mp4")
        if os.path.exists(file_path):
            files.append(f"/static/manuals/{folder_name}/{i}.mp4")
        else:
            break

    return jsonify({ "files": files })

@app.route("/update_manual", methods=["POST"])
def update_manual():
    title = request.args.get("title", "")
    folder_name = sanitize_foldername(title)
    manual_path = os.path.join(MANUAL_DIR, folder_name)

    if not os.path.exists(manual_path):
        return "手順書が存在しません", 404

    # 既存 .mp4 削除
    for f in os.listdir(manual_path):
        if f.endswith(".mp4"):
            os.remove(os.path.join(manual_path, f))

    # アップロードされたファイルを 1.mp4, 2.mp4, ... に保存し直す
    i = 1
    for f in request.files.getlist("videos"):
        f.save(os.path.join(manual_path, f"{i}.mp4"))
        i += 1

    return "", 204


@app.route("/manuals")
def get_manuals():
    if os.path.exists(INDEX_FILE):
        with open(INDEX_FILE, "r", encoding="utf-8") as f:
            manuals = json.load(f)
        # 実在するフォルダのみ返す（正確なパスで確認）
        filtered = []
        for m in manuals:
            folder = os.path.join(app.root_path, "static", m["path"])
            if os.path.isdir(folder):
                filtered.append(m)
        return jsonify({"manuals": filtered})
    else:
        return jsonify({"manuals": []})
    
@app.route("/delete_manual", methods=["POST"])
def delete_manual():
    title = request.form.get("title", "")
    folder_name = None

    # manual_index.json から path を取得
    if os.path.exists(INDEX_FILE):
        with open(INDEX_FILE, "r", encoding="utf-8") as f:
            manuals = json.load(f)
        # 該当手順書を検索
        for m in manuals:
            if m["title"] == title:
                folder_name = m["path"]  # 例: manuals/見本
                break

        # path が見つかれば削除
        if folder_name:
            folder_path = os.path.join(app.root_path, "static", folder_name)
            if os.path.exists(folder_path):
                shutil.rmtree(folder_path)

        # manual_index.json からも削除
        manuals = [m for m in manuals if m["title"] != title]
        with open(INDEX_FILE, "w", encoding="utf-8") as f:
            json.dump(manuals, f, ensure_ascii=False, indent=2)

    return "", 204



if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
