import cv2
import numpy as np
import requests
import sys
import time
import subprocess
import pandas as pd
import os
from os.path import join, abspath, dirname, exists
from datetime import datetime

'''
このスクリプトは以下の機能を持ちます:
1. ESP32カメラの映像をリアルタイムで表示します。
2. 最新のスナップショットを常に上書き保存します。
3. 'log/(年)/(月)' フォルダを自動作成し、過去の写真を日付フォルダに分けてすべて保存します。
4. カメラの状態ログ(CSV)を保存します（新しいものが一番上に来るように）。
5. 保存した画像とCSVファイルをGitHubに自動でプッシュします。
'''

# ==============================================================================
# === 設定項目 (ここをあなたの環境に合わせて変更してください) ===
# ==============================================================================
# ESP32カメラのIPアドレス
ESP32_IP_ADDRESS = "192.168.137.50"
# 映像ストリームの形式 ("rtsp" または "http")
STREAM_TYPE = "rtsp"

# 保存するファイル名
SNAPSHOT_IMAGE_FILE = "snapshot.jpg"
SNAPSHOT_FILE_PREFIX = "snapshot"
LOG_CSV_FILE = "camera_log.csv"

# 定期的に保存・プッシュする間隔（秒）
UPDATE_INTERVAL = 60
# ==============================================================================

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
    print("[CSV] ログファイルを更新します...")
    try:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        new_log_df = pd.DataFrame([{"timestamp": timestamp, "camera_ip": ip, "status": status, "snapshot_file": image_file}])
        if exists(CSV_PATH):
            existing_df = pd.read_csv(CSV_PATH)
            combined_df = pd.concat([new_log_df, existing_df], ignore_index=True)
            combined_df.to_csv(CSV_PATH, index=False, encoding='utf-8-sig')
            print(f"[CSV] {LOG_CSV_FILE} の先頭に情報を追記しました。")
        else:
            new_log_df.to_csv(CSV_PATH, index=False, encoding='utf-8-sig')
            print(f"[CSV] {LOG_CSV_FILE} を新規作成しました。")
    except PermissionError:
        print(f"[CSV ERROR] 書き込みが拒否されました。'{LOG_CSV_FILE}'がExcelなどで開かれていないか確認してください。")
    except Exception as e:
        print(f"[CSV ERROR] CSVファイルの書き込みに失敗しました: {e}")


# === Gitへコミットとプッシュを行う関数 (変更なし) ===
def git_commit_and_push():
    print("[GIT] GitHubへ変更をプッシュします...")
    try:
        commit_message = f"Auto-update: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        subprocess.run(["git", "add", "."], check=True, cwd=BASE_DIR)
        subprocess.run(["git", "commit", "-m", commit_message], check=True, cwd=BASE_DIR)
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
            cv2.imshow("ESP32 Camera Stream (Live)", frame)
        else:
            print("[WARN] フレームを取得できませんでした。カメラとの接続を確認してください。")
            camera_status = "OFFLINE"
            time.sleep(1)
            continue

        if time.monotonic() - last_update_time >= UPDATE_INTERVAL:
            print(f"\n--- 定期処理開始 ({datetime.now().strftime('%H:%M:%S')}) ---")
            
            main_snapshot_path = join(BASE_DIR, SNAPSHOT_IMAGE_FILE)
            cv2.imwrite(main_snapshot_path, frame)
            print(f"[SAVE] {SNAPSHOT_IMAGE_FILE} を更新しました。")

            # ★★★ 確認用の処理を追加 ★★★
            # 保存したばかりのファイルをディスクから読み込んで、更新されているか確認する
            try:
                saved_frame = cv2.imread(main_snapshot_path)
                if saved_frame is not None:
                    # 確認用の別ウィンドウに表示
                    cv2.imshow("Saved Snapshot (from file)", saved_frame)
                else:
                    print("[VERIFY] 確認用の画像読み込みに失敗しました。")
            except Exception as e:
                print(f"[VERIFY ERROR] 確認処理中にエラーが発生: {e}")
            
            # --- ここから下のアーカイブ保存、CSV、Git処理は変更なし ---
            now = datetime.now()
            year_str = now.strftime('%Y')
            month_str = now.strftime('%m')
            archive_dir_path = join(BASE_DIR, "log", year_str, month_str)
            os.makedirs(archive_dir_path, exist_ok=True)
            timestamp_str = now.strftime('%Y%m%d_%H%M%S')
            archive_filename = f"{SNAPSHOT_FILE_PREFIX}_{timestamp_str}.jpg"
            archive_full_path = join(archive_dir_path, archive_filename)
            cv2.imwrite(archive_full_path, frame)
            relative_archive_dir = join("log", year_str, month_str).replace(os.sep, '/')
            print(f"[ARCHIVE] {archive_filename} を {relative_archive_dir} に保存しました。")
            csv_record_path = join(relative_archive_dir, archive_filename).replace(os.sep, '/')
            update_log_csv(camera_status, ESP32_IP_ADDRESS, csv_record_path)
            git_commit_and_push()

            last_update_time = time.monotonic()
            print("--- 定期処理完了 ---\n")

        key = cv2.waitKey(1)
        if key == 27:
            break
    
    print("終了します。")
    esp1.destroy()
