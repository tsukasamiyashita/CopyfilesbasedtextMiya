import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import os
import shutil
import threading
from pathlib import Path
import concurrent.futures

# --- 検索・コピー処理関数 ---
def process_single_file(filepath, keywords, dst_folder):
    """
    1ファイルを処理する関数。
    ファイル名にキーワードが含まれているかを確認し、含まれていればコピーする。
    """
    try:
        # ファイル名を取得 (拡張子含む)
        filename = filepath.name
        
        # キーワードがファイル名に含まれているかチェック
        matched_kw = None
        for kw in keywords:
            if kw in filename:
                matched_kw = kw
                break
        
        # ヒットしなければ終了
        if matched_kw is None:
            return None

        # --- コピー実行 ---
        target_file = dst_folder / filename
        
        # 同名ファイル回避 (例: text.txt -> text_1.txt)
        if target_file.exists():
            base = target_file.stem
            ext = target_file.suffix
            idx = 1
            while target_file.exists():
                target_file = dst_folder / f"{base}_{idx}{ext}"
                idx += 1
        
        shutil.copy2(filepath, target_file)
        return ("COPIED", f"{filename} (ヒット: {matched_kw})")

    except Exception as e:
        return ("ERROR", f"{filepath.name}: {str(e)}")

# --- アプリケーション本体 ---
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("ファイル名検索・コピーツール")
        self.geometry("600x650")

        # --- UI構築 ---
        # 1. 検索キーワード
        tk.Label(self, text="検索したいファイル名の一部 (1行に1つ)", anchor="w").pack(fill="x", padx=10, pady=(10, 0))
        self.txt_keywords = scrolledtext.ScrolledText(self, height=6)
        self.txt_keywords.pack(fill="x", padx=10, pady=5)

        # 2. フォルダ選択エリア
        self.create_folder_select_ui("検索元フォルダ:", "src_path")
        self.create_folder_select_ui("コピー先フォルダ:", "dst_path")

        # 3. 実行ボタン
        self.btn_run = tk.Button(self, text="検索とコピーを実行", command=self.start_process, bg="#dddddd", height=2)
        self.btn_run.pack(fill="x", padx=10, pady=10)

        # 4. ログ表示
        tk.Label(self, text="実行ログ", anchor="w").pack(fill="x", padx=10)
        self.txt_log = scrolledtext.ScrolledText(self, state='disabled')
        self.txt_log.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    def create_folder_select_ui(self, label_text, attr_name):
        frame = tk.Frame(self)
        frame.pack(fill="x", padx=10, pady=5)
        tk.Label(frame, text=label_text, width=15, anchor="w").pack(side="left")
        entry = tk.Entry(frame)
        entry.pack(side="left", fill="x", expand=True)
        setattr(self, f"entry_{attr_name}", entry)
        tk.Button(frame, text="参照", command=lambda: self.select_folder(entry)).pack(side="left", padx=(5, 0))

    def select_folder(self, entry_widget):
        path = filedialog.askdirectory()
        if path:
            entry_widget.delete(0, tk.END)
            entry_widget.insert(0, path)

    # --- UI操作用 (スレッドセーフ) ---
    def append_log(self, message):
        self.txt_log.config(state='normal')
        self.txt_log.insert(tk.END, message + "\n")
        self.txt_log.see(tk.END)
        self.txt_log.config(state='disabled')

    def ui_finish(self, count):
        self.append_log(f"--- 完了: {count}ファイルをコピーしました ---")
        self.btn_run.config(state='normal')
        messagebox.showinfo("完了", f"処理が完了しました。\nコピー数: {count}")

    # --- メイン処理 ---
    def start_process(self):
        # 入力キーワードの取得
        raw_text = self.txt_keywords.get("1.0", tk.END)
        keywords = [line.strip() for line in raw_text.splitlines() if line.strip()]
        
        src = self.entry_src_path.get()
        dst = self.entry_dst_path.get()

        if not keywords:
            messagebox.showwarning("警告", "検索キーワードを入力してください")
            return
        if not src or not os.path.isdir(src):
            messagebox.showwarning("警告", "有効な検索元フォルダを指定してください")
            return
        if not dst or not os.path.isdir(dst):
            messagebox.showwarning("警告", "有効なコピー先フォルダを指定してください")
            return

        # UIロック
        self.btn_run.config(state='disabled')
        self.txt_log.config(state='normal')
        self.txt_log.delete("1.0", tk.END)
        self.txt_log.config(state='disabled')
        self.append_log(f"--- ファイル名検索開始: キーワード {len(keywords)}件 ---")
        
        # スレッド開始
        threading.Thread(target=self.run_parallel_task, args=(keywords, src, dst), daemon=True).start()

    def run_parallel_task(self, keywords, src, dst):
        src_path_obj = Path(src).resolve()
        dst_path_obj = Path(dst).resolve()
        
        # 1. ファイルリストアップ
        all_files = []
        for root, dirs, files in os.walk(src):
            current_dir = Path(root).resolve()
            # コピー先フォルダが検索元に含まれる場合は除外
            if dst_path_obj == current_dir or dst_path_obj in current_dir.parents:
                continue
            for f in files:
                all_files.append(current_dir / f)

        self.after(0, self.append_log, f"対象ファイル数: {len(all_files)}件 - 解析中...")

        copied_count = 0
        
        # 2. 並列処理実行
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future_to_file = {
                executor.submit(process_single_file, f, keywords, dst_path_obj): f 
                for f in all_files
            }

            for future in concurrent.futures.as_completed(future_to_file):
                result = future.result()
                if result:
                    status, msg = result
                    if status == "COPIED":
                        copied_count += 1
                        self.after(0, self.append_log, f"コピー: {msg}")
                    elif status == "ERROR":
                         # エラーログが必要な場合はここで出力
                         pass

        self.after(0, self.ui_finish, copied_count)

if __name__ == "__main__":
    app = App()
    app.mainloop()