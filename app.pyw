import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, font
import os
import shutil
import threading
from pathlib import Path
import concurrent.futures

# --- デザイン設定 (Color Palette & Style) ---
class Theme:
    BG_MAIN = "#F0F4F8"       # 全体の背景（薄い青グレー）
    BG_Input = "#FFFFFF"      # 入力エリア背景
    FG_TEXT = "#2C3E50"       # メインテキスト色（濃紺グレー）
    FG_SUB = "#95A5A6"        # 補足・バージョン情報色（薄いグレー）
    
    BTN_PRIMARY = "#3498DB"   # 実行ボタン（明るい青）
    BTN_PRIMARY_HOVER = "#2980B9" # 実行ボタンホバー（濃い青）
    BTN_DANGER = "#E74C3C"    # 中止ボタン（赤）
    BTN_DANGER_HOVER = "#C0392B" # 中止ボタンホバー
    BTN_SUB = "#BDC3C7"       # 参照ボタン（グレー）
    BTN_SUB_HOVER = "#95A5A6" # 参照ボタンホバー
    
    FONT_MAIN = ("Yu Gothic UI", 10)
    FONT_BOLD = ("Yu Gothic UI", 10, "bold")
    FONT_SMALL = ("Yu Gothic UI", 9)

# --- 安全な検索・コピー処理関数 ---
def process_single_file_safely(filepath, keywords, dst_folder):
    """
    1ファイルを処理する関数 (厳重な保護付き)。
    """
    try:
        src_path = filepath.resolve()
        filename = src_path.name
        
        # --- 1. キーワード判定 ---
        matched_kw = None
        for kw in keywords:
            if kw in filename:
                matched_kw = kw
                break
        
        if matched_kw is None:
            return None

        # --- 2. 安全性チェック ---
        target_file = (dst_folder / filename).resolve()
        
        if src_path == target_file:
            return ("SKIPPED", f"{filename} (同一ファイル)")
            
        try:
            if os.path.samefile(src_path, target_file):
                 return ("SKIPPED", f"{filename} (同一ファイル)")
        except OSError:
            pass

        # --- 3. 更新判定 ---
        action_type = "COPIED"

        if target_file.exists():
            src_mtime = src_path.stat().st_mtime
            dst_mtime = target_file.stat().st_mtime

            if src_mtime > dst_mtime:
                action_type = "UPDATED"
            else:
                return ("SKIPPED", f"{filename} (既存の方が新しいか同じ)")
        
        # --- 4. コピー実行 ---
        shutil.copy2(src_path, target_file)
        
        return (action_type, f"{filename} (ヒット: {matched_kw})")

    except PermissionError:
        return ("ERROR", f"{filepath.name}: 権限なし")
    except Exception as e:
        return ("ERROR", f"{filepath.name}: {str(e)}")

# --- UIパーツ: ホバー機能付きボタン ---
class HoverButton(tk.Button):
    def __init__(self, master, bg_color, hover_color, text_color="#FFFFFF", **kwargs):
        super().__init__(master, bg=bg_color, fg=text_color, activebackground=hover_color, activeforeground=text_color, relief="flat", borderwidth=0, cursor="hand2", **kwargs)
        self.bg_color = bg_color
        self.hover_color = hover_color
        self.bind("<Enter>", self.on_enter)
        self.bind("<Leave>", self.on_leave)

    def on_enter(self, e):
        self['background'] = self.hover_color

    def on_leave(self, e):
        self['background'] = self.bg_color
    
    def set_color(self, bg, hover):
        self.bg_color = bg
        self.hover_color = hover
        self['background'] = bg
        self['activebackground'] = hover

# --- アプリケーション本体 ---
class App(tk.Tk):
    APP_VERSION = "v1.0.0"
    
    CHANGELOG = f"""【バージョン情報】
CopyfilesbasedtextMiya {APP_VERSION}

指定したキーワードがファイル名に含まれるファイルを安全にコピー・バックアップするツールです。
"""

    README = """【使い方 / README】

1. 検索キーワードを入力します（1行に1つ）。
   ※右クリックメニューからの貼り付けにも対応しています。
2. 「検索元フォルダ」と「コピー先フォルダ」をそれぞれ参照ボタンから指定します。
3. 「検索とコピーを開始」ボタンをクリックすると処理が始まります。

【主な機能と仕様】
・ファイル名検索: 入力したキーワード（部分一致）でファイルを高速検索します。
・安全コピー保護: 読み取り専用アクセスで元ファイルを保護し、誤った上書きを防ぎます。
・差分更新機能: コピー先に既に同名ファイルが存在する場合、コピー元の方が「新しい場合のみ」上書き更新します。
・中断機能: 処理中であっても「処理を中止する」ボタンから安全に中断できます。
"""

    def __init__(self):
        super().__init__()
        # タイトル変更
        self.title(f"CopyfilesbasedtextMiya {self.APP_VERSION}")
        self.geometry("600x750") # 高さを少し拡張
        self.configure(bg=Theme.BG_MAIN)
        
        # スレッド制御
        self.stop_event = threading.Event()
        self.is_running = False

        # --- メニューバー作成 ---
        self._create_menu()

        # --- UI構築 ---
        container = tk.Frame(self, bg=Theme.BG_MAIN)
        container.pack(fill="both", expand=True, padx=20, pady=20)

        # ---------------------------------------------------------
        # レイアウト配置順序の最適化
        # Tkinterのpackは「早い者勝ち」で場所を確保するため、
        # 上部固定 → 下部固定(バージョン) → 中央可変(ログ) の順で配置します。
        # ---------------------------------------------------------

        # 1. [Top] 検索キーワードエリア
        lbl_kw = tk.Label(container, text="検索キーワード (ファイル名の一部)", bg=Theme.BG_MAIN, fg=Theme.FG_TEXT, font=Theme.FONT_BOLD, anchor="w")
        lbl_kw.pack(side="top", fill="x", pady=(0, 5))
        
        tk.Label(container, text="※1行に1つ入力 / 右クリック貼り付け可", bg=Theme.BG_MAIN, fg=Theme.FG_SUB, font=("Yu Gothic UI", 8), anchor="w").pack(side="top", fill="x", pady=(0, 2))

        self.txt_keywords = scrolledtext.ScrolledText(container, height=6, bg=Theme.BG_Input, fg=Theme.FG_TEXT, font=Theme.FONT_MAIN, relief="flat", bd=1)
        self.txt_keywords.pack(side="top", fill="x", pady=(0, 15))
        self.add_border(self.txt_keywords)
        self.add_context_menu(self.txt_keywords)

        # 2. [Top] フォルダ選択エリア
        self.create_folder_select_ui(container, "検索元フォルダ (読取専用)", "src_path")
        self.create_folder_select_ui(container, "コピー先フォルダ (保存先)", "dst_path")

        # 3. [Top] 実行/中止ボタン
        self.btn_run = HoverButton(container, text="検索とコピーを開始", 
                                   bg_color=Theme.BTN_PRIMARY, hover_color=Theme.BTN_PRIMARY_HOVER,
                                   font=Theme.FONT_BOLD, height=2)
        self.btn_run.configure(command=self.toggle_process)
        self.btn_run.pack(side="top", fill="x", pady=(10, 20))

        # 4. [Bottom] バージョン情報 (ここを先に配置して場所を確保)
        lbl_version = tk.Label(container, text=self.APP_VERSION, bg=Theme.BG_MAIN, fg=Theme.FG_SUB, font=Theme.FONT_SMALL, anchor="e")
        lbl_version.pack(side="bottom", fill="x", pady=(5, 0))

        # 5. [Center] ログ表示 (残りのスペースを全て埋める)
        # タイトル
        tk.Label(container, text="実行ログ", bg=Theme.BG_MAIN, fg=Theme.FG_TEXT, font=Theme.FONT_BOLD, anchor="w").pack(side="top", fill="x", pady=(0, 5))
        
        # ログ本体
        self.txt_log = scrolledtext.ScrolledText(container, state='disabled', bg=Theme.BG_Input, fg=Theme.FG_TEXT, font=("Consolas", 9), relief="flat")
        self.txt_log.pack(side="top", fill="both", expand=True) # expand=Trueで残り領域を占有
        self.add_border(self.txt_log)
        self.add_context_menu(self.txt_log)

    def _create_menu(self):
        menubar = tk.Menu(self)
        
        # ヘルプメニュー
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="使い方 / README", command=self.show_readme_info)
        help_menu.add_command(label="バージョン情報", command=self.show_version_info)
        
        menubar.add_cascade(label="ヘルプ", menu=help_menu)
        self.config(menu=menubar)

    def show_version_info(self):
        messagebox.showinfo("バージョン情報", self.CHANGELOG)

    def show_readme_info(self):
        messagebox.showinfo("使い方 / README", self.README)

    def add_border(self, widget):
        """ウィジェットの周りに1pxの枠線フレームをつける"""
        widget.config(highlightbackground="#D0D9E0", highlightcolor=Theme.BTN_PRIMARY, highlightthickness=1)

    def create_folder_select_ui(self, parent, label_text, attr_name):
        frame = tk.Frame(parent, bg=Theme.BG_MAIN)
        frame.pack(side="top", fill="x", pady=(0, 10))
        
        lbl = tk.Label(frame, text=label_text, width=22, anchor="w", bg=Theme.BG_MAIN, fg=Theme.FG_TEXT, font=Theme.FONT_MAIN)
        lbl.pack(side="left")
        
        entry = tk.Entry(frame, bg=Theme.BG_Input, fg=Theme.FG_TEXT, font=Theme.FONT_MAIN, relief="flat", highlightbackground="#D0D9E0", highlightcolor=Theme.BTN_PRIMARY, highlightthickness=1)
        entry.pack(side="left", fill="x", expand=True, ipady=4, padx=(0, 5))
        self.add_context_menu(entry)
        setattr(self, f"entry_{attr_name}", entry)
        
        btn = HoverButton(frame, text="参照", bg_color=Theme.BTN_SUB, hover_color=Theme.BTN_SUB_HOVER, width=8, font=Theme.FONT_MAIN)
        btn.configure(command=lambda: self.select_folder(entry))
        btn.pack(side="left")

    def add_context_menu(self, widget):
        menu = tk.Menu(widget, tearoff=0, bg="white", fg=Theme.FG_TEXT)
        menu.add_command(label="切り取り", command=lambda: widget.event_generate("<<Cut>>"))
        menu.add_command(label="コピー", command=lambda: widget.event_generate("<<Copy>>"))
        menu.add_command(label="貼り付け", command=lambda: widget.event_generate("<<Paste>>"))
        menu.add_separator()
        menu.add_command(label="全選択", command=lambda: widget.event_generate("<<SelectAll>>"))

        def show_menu(event):
            try:
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                menu.grab_release()

        if self.tk.call('tk', 'windowingsystem') == 'aqua':
            widget.bind("<Button-2>", show_menu)
            widget.bind("<Control-1>", show_menu)
        else:
            widget.bind("<Button-3>", show_menu)

    def select_folder(self, entry_widget):
        current_path = entry_widget.get().strip()
        init_dir = os.path.expanduser("~")
        if current_path and os.path.isdir(current_path):
            init_dir = current_path
        
        path = filedialog.askdirectory(initialdir=init_dir)
        if path:
            entry_widget.delete(0, tk.END)
            entry_widget.insert(0, path)

    # --- UI操作 (スレッドセーフ) ---
    def append_log(self, message):
        self.txt_log.config(state='normal')
        self.txt_log.insert(tk.END, message + "\n")
        self.txt_log.see(tk.END)
        self.txt_log.config(state='disabled')

    def set_ui_state(self, running):
        self.is_running = running
        if running:
            self.btn_run.configure(text="処理を中止する")
            self.btn_run.set_color(Theme.BTN_DANGER, Theme.BTN_DANGER_HOVER)
        else:
            self.btn_run.configure(text="検索とコピーを開始")
            self.btn_run.set_color(Theme.BTN_PRIMARY, Theme.BTN_PRIMARY_HOVER)

    def ui_finish(self, counts, aborted=False):
        self.set_ui_state(False)
        if aborted:
            self.append_log("!!! 中止されました !!!")
            messagebox.showinfo("中止", "処理を中止しました。")
        else:
            self.append_log(f"--- 完了 ---")
            self.append_log(f"新規: {counts.get('COPIED', 0)}")
            self.append_log(f"更新: {counts.get('UPDATED', 0)}")
            self.append_log(f"維持: {counts.get('SKIPPED', 0)}")
            
            msg = (f"処理完了\n"
                   f"新規: {counts.get('COPIED', 0)}\n"
                   f"更新: {counts.get('UPDATED', 0)}\n"
                   f"維持: {counts.get('SKIPPED', 0)}")
            messagebox.showinfo("完了", msg)

    # --- ボタンアクション ---
    def toggle_process(self):
        if self.is_running:
            if messagebox.askyesno("確認", "処理を中止しますか？"):
                self.stop_event.set()
                self.append_log("...中止要求中...")
        else:
            self.start_process()

    # --- メイン処理 ---
    def start_process(self):
        raw_text = self.txt_keywords.get("1.0", tk.END)
        keywords = [line.strip() for line in raw_text.splitlines() if line.strip()]
        
        src = self.entry_src_path.get()
        dst = self.entry_dst_path.get()

        if not keywords:
            messagebox.showwarning("入力エラー", "検索キーワードを入力してください")
            return
        if not src or not os.path.isdir(src):
            messagebox.showwarning("入力エラー", "検索元フォルダを指定してください")
            return
        if not dst or not os.path.isdir(dst):
            messagebox.showwarning("入力エラー", "コピー先フォルダを指定してください")
            return

        self.stop_event.clear()
        self.set_ui_state(True)
        
        self.txt_log.config(state='normal')
        self.txt_log.delete("1.0", tk.END)
        self.txt_log.config(state='disabled')
        self.append_log(f"--- 検索開始 ---")
        
        threading.Thread(target=self.run_parallel_task, args=(keywords, src, dst), daemon=True).start()

    def run_parallel_task(self, keywords, src, dst):
        src_path_obj = Path(src).resolve()
        dst_path_obj = Path(dst).resolve()
        
        if src_path_obj == dst_path_obj:
            self.after(0, self.append_log, "エラー: 検索元とコピー先が同じです")
            self.after(0, self.ui_finish, {}, True)
            return

        all_files = []
        for root, dirs, files in os.walk(src):
            if self.stop_event.is_set(): break
            current_dir = Path(root).resolve()
            if dst_path_obj == current_dir or dst_path_obj in current_dir.parents:
                continue
            for f in files:
                all_files.append(current_dir / f)

        if self.stop_event.is_set():
            self.after(0, self.ui_finish, {}, True)
            return

        self.after(0, self.append_log, f"対象ファイル: {len(all_files)}件 - 解析中...")

        stats = {"COPIED": 0, "UPDATED": 0, "SKIPPED": 0}
        aborted = False
        
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future_to_file = {
                executor.submit(process_single_file_safely, f, keywords, dst_path_obj): f 
                for f in all_files
            }

            for future in concurrent.futures.as_completed(future_to_file):
                if self.stop_event.is_set():
                    aborted = True
                    for f in future_to_file: f.cancel()
                    break

                try:
                    result = future.result()
                    if result:
                        status, msg = result
                        if status in stats:
                            stats[status] += 1
                        
                        if status != "SKIPPED":
                            disp_status = "新規" if status == "COPIED" else "更新"
                            self.after(0, self.append_log, f"[{disp_status}] {msg}")
                except Exception:
                    pass
                    
        self.after(0, self.ui_finish, stats, aborted)

if __name__ == "__main__":
    app = App()
    app.mainloop()