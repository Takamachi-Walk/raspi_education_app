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
    invalid = '\\/:*?\"<>|'
    for c in invalid:
        name = name.replace(c, '-')
    return name.strip() or "manual"

# --- 動画手順書登録 ---
@app.route("/register_manual", methods=["POST"])
def register_manual():
    title = request.form.get("title", "").strip()
    if not title:
        return "タイトルがありません", 400

    folder = sanitize_foldername(title)
    manual_path = os.path.join(MANUAL_DIR, folder)
    os.makedirs(manual_path, exist_ok=True)

    files = request.files.getlist("videos")
    for i, file in enumerate(files):
        file.save(os.path.join(manual_path, f"{i + 1}.mp4"))

    if os.path.exists(INDEX_FILE):
        with open(INDEX_FILE, "r", encoding="utf-8") as f:
            index = json.load(f)
    else:
        index = []

    index = [m for m in index if m["title"] != title]
    index.append({
        "title": title,
        "path": f"manuals/{folder}"
    })

    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    return "OK"

@app.route("/register_manual")
def register_manual_page():
    return render_template("register_manual.html")

@app.route("/gpio_status")
def gpio_status():
    return jsonify({
        "gpio17": GPIO.input(17) if GPIO_AVAILABLE else 0,
        "gpio27": GPIO.input(27) if GPIO_AVAILABLE else 0
    })

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
        old_title = request.args.get("oldTitle", "")
        old_folder = sanitize_foldername(old_title)
        old_path = os.path.join(MANUAL_DIR, old_folder)
        if os.path.exists(old_path):
            folder_name = old_folder
            manual_path = old_path
        else:
            return "指定された手順書が見つかりません", 404

    files = []
    for i in range(1, 100):
        file_path = os.path.join(manual_path, f"{i}.mp4")
        if os.path.exists(file_path):
            files.append(f"/static/manuals/{folder_name}/{i}.mp4")
        else:
            break

    return jsonify({ "files": files })

@app.route("/update_manual", methods=["POST"])
def update_manual():
    title = request.form.get("title", "").strip()
    old_title = request.form.get("oldTitle", "").strip()

    if not title or not old_title:
        return "title or oldTitle missing", 400

    folder_name = sanitize_foldername(old_title)
    manual_path = os.path.join(MANUAL_DIR, folder_name)

    if not os.path.exists(manual_path):
        return "手順書が存在しません", 404

    new_folder = sanitize_foldername(title)
    new_path = os.path.join(MANUAL_DIR, new_folder)

    if folder_name != new_folder:
        if os.path.exists(new_path):
            return "同名の手順書が既に存在します", 400
        os.rename(manual_path, new_path)
        manual_path = new_path

    for i in range(1, 100):
        file_path = os.path.join(manual_path, f"{i}.mp4")
        if os.path.exists(file_path):
            os.remove(file_path)
        else:
            break

    files = request.files.getlist("videos")
    os.makedirs(manual_path, exist_ok=True)
    for i, file in enumerate(files):
        file.save(os.path.join(manual_path, f"{i + 1}.mp4"))

    if os.path.exists(INDEX_FILE):
        with open(INDEX_FILE, "r", encoding="utf-8") as f:
            index = json.load(f)
    else:
        index = []

    index = [m for m in index if m["title"] != old_title]
    index.append({
        "title": title,
        "path": f"manuals/{new_folder}"
    })

    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    return "OK"

@app.route("/manuals")
def get_manuals():
    if not os.path.exists(INDEX_FILE):
        return jsonify({ "manuals": [] })

    with open(INDEX_FILE, "r", encoding="utf-8") as f:
        manuals = json.load(f)

    return jsonify({ "manuals": manuals })

@app.route("/delete_manual", methods=["POST"])
def delete_manual():
    title = request.form.get("title", "")
    folder_name = None

    if os.path.exists(INDEX_FILE):
        with open(INDEX_FILE, "r", encoding="utf-8") as f:
            manuals = json.load(f)

        for m in manuals:
            if m["title"] == title:
                folder_name = m["path"]
                break

        if folder_name:
            folder_path = os.path.join(app.root_path, "static", folder_name)
            if os.path.exists(folder_path):
                shutil.rmtree(folder_path)

        manuals = [m for m in manuals if m["title"] != title]
        with open(INDEX_FILE, "w", encoding="utf-8") as f:
            json.dump(manuals, f, ensure_ascii=False, indent=2)

    return "", 204

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
