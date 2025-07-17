import cv2
import numpy as np
import requests
import sys
import time
import subprocess
import pandas as pd
from os.path import join, abspath, dirname, exists
from datetime import datetime

'''
このスクリプトは以下の機能を持ちます:
1. ESP32カメラの映像をリアルタイムで表示します。
2. 定期的にスナップショット画像とカメラの状態ログ(CSV)を保存します。
3. 保存した画像とCSVファイルをGitHubに自動でプッシュします。
'''

# ==============================================================================
# === 設定項目 (ここをあなたの環境に合わせて変更してください) ===
# ==============================================================================
# ESP32カメラのIPアドレス
ESP32_IP_ADDRESS = "192.168.137.50"
# 映像ストリームの形式 ("rtsp" または "http")
STREAM_TYPE = "rtsp"

# ★★★ 変更点: 保存するファイル名の「接頭辞」を設定 ★★★
SNAPSHOT_FILE_PREFIX = "snapshot"
LOG_CSV_FILE = "camera_log.csv"

# 定期的に保存・プッシュする間隔（秒）
UPDATE_INTERVAL = 10
# ==============================================================================

# --- ファイルパスを自動生成 ---
BASE_DIR = abspath(dirname(__file__))
CSV_PATH = join(BASE_DIR, LOG_CSV_FILE)


# === ESP32カメラ操作クラス (変更なし) ===
class ESP32Getter():
    def __init__(self, url, type="rtsp") -> None:
        self.url = url
        if(type=="http"):
            self.cap = cv2.VideoCapture(f"http://{self.url}")
        elif(type=="rtsp"):
            self.cap = cv2.VideoCapture(f"rtsp://{self.url}:554/mjpeg/1")
        else:
            print(f"Error: Unsupported type '{type}'")
            sys.exit()
        
        if not self.cap.isOpened():
            print(f"エラー: カメラ({self.url})に接続できませんでした。IPアドレスやネットワークを確認してください。")
            sys.exit()
            
        self.set_resolution(index=8)

    def set_resolution(self, index: int=1):
        try:
            requests.get(f"http://{self.url}/control?var=framesize&val={index}")
        except Exception as e:
            print(f"SET_RESOLUTION: 解像度の設定に失敗しました - {e}")

    def get_frame(self):
        success, frame = self.cap.read()
        return frame if success else None
    
    def destroy(self):
        self.cap.release()
        cv2.destroyAllWindows()


# === CSVログを更新する関数 (変更なし) ===
def update_log_csv(status: str, ip: str, image_file: str):
    """
    カメラの状態をCSVファイルに追記する
    """
    print("[CSV] ログファイルを更新します...")
    try:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        new_log = pd.DataFrame([{"timestamp": timestamp, "camera_ip": ip, "status": status, "snapshot_file": image_file}])
        if not exists(CSV_PATH):
            new_log.to_csv(CSV_PATH, index=False, encoding='utf-8-sig')
            print(f"[CSV] {LOG_CSV_FILE} を新規作成しました。")
        else:
            new_log.to_csv(CSV_PATH, mode='a', header=False, index=False, encoding='utf--sig')
            print(f"[CSV] {LOG_CSV_FILE} に情報を追記しました。")
    except PermissionError:
        # ★★★ 改善点: パーミッションエラーの場合に分かりやすいメッセージを表示 ★★★
        print(f"[CSV ERROR] 書き込みが拒否されました。'{LOG_CSV_FILE}'がExcelなどで開かれていないか確認してください。")
    except Exception as e:
        print(f"[CSV ERROR] CSVファイルの書き込みに失敗しました: {e}")


# === Gitへコミットとプッシュを行う関数 ===
def git_commit_and_push():
    """
    ★★★ 改善点: フォルダ内のすべての変更をGitにコミットし、プッシュする ★★★
    """
    print("[GIT] GitHubへ変更をプッシュします...")
    try:
        commit_message = f"Auto-update: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        # 1. git add . (カレントディレクトリのすべての変更を追加)
        subprocess.run(["git", "add", "."], check=True, cwd=BASE_DIR)
        
        # 2. git commit
        subprocess.run(["git", "commit", "-m", commit_message], check=True, cwd=BASE_DIR)
        
        # 3. git push
        subprocess.run(["git", "push", "origin", "main"], check=True, cwd=BASE_DIR)
        
        print("[GIT] Push 成功！")

    except FileNotFoundError:
         print("[GIT ERROR] 'git'コマンドが見つかりません。Gitがインストールされ、PATHが通っているか確認してください。")
    except subprocess.CalledProcessError as e:
        if "nothing to commit" in str(e.stderr) or "nothing to commit" in str(e.stdout):
             print("[GIT] 変更がなかったため、コミットはスキップされました。")
        else:
            print(f"[GIT ERROR] Pushに失敗しました: {e}")


# === メインの実行部分 ===
if __name__ == '__main__':
    esp1 = ESP32Getter(ESP32_IP_ADDRESS, type=STREAM_TYPE)
    last_update_time = time.monotonic() - UPDATE_INTERVAL

    print("カメラ映像を表示します。ESCキーで終了します。")
    print(f"{UPDATE_INTERVAL}秒ごとにスナップショットとログをGitHubにプッシュします。")

    while True:
        frame = esp1.get_frame()
        camera_status = "ONLINE"

        if frame is not None:
            cv2.imshow("ESP32 Camera Stream", frame)
        else:
            print("[WARN] フレームを取得できませんでした。カメラとの接続を確認してください。")
            camera_status = "OFFLINE"
            time.sleep(1)
            continue # フレームがなければ以降の処理はスキップ

        if time.monotonic() - last_update_time >= UPDATE_INTERVAL:
            print(f"\n--- 定期処理開始 ({datetime.now().strftime('%H:%M:%S')}) ---")
            
            # ★★★ 変更点: タイムスタンプ付きのユニークなファイル名を生成 ★★★
            timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
            unique_image_file = f"{SNAPSHOT_FILE_PREFIX}_{timestamp_str}.jpg"
            unique_image_path = join(BASE_DIR, unique_image_file)
            
            # 画像をユニークな名前で保存
            cv2.imwrite(unique_image_path, frame)
            print(f"[SAVE] {unique_image_file} を保存しました。")
            
            # CSVログを更新 (ユニークなファイル名を渡す)
            update_log_csv(camera_status, ESP32_IP_ADDRESS, unique_image_file)
            
            # Gitへプッシュ (フォルダ内のすべての変更が対象)
            git_commit_and_push()

            last_update_time = time.monotonic()
            print("--- 定期処理完了 ---\n")

        key = cv2.waitKey(1)
        if key == 27:
            break
    
    print("終了します。")
    esp1.destroy()
