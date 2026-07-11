"""
MP3 播放速度调整工具（GUI 版 + 拖放支持）
使用 ffmpeg 的 atempo 滤镜实现变速不变调
"""

import shutil
import subprocess
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path

from tkinterdnd2 import DND_FILES, TkinterDnD


CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def available_output_path(source: Path) -> Path:
    """生成不会覆盖已有文件的输出路径。"""
    candidate = source.with_name(f"{source.stem}_fast{source.suffix}")
    index = 2
    while candidate.exists():
        candidate = source.with_name(f"{source.stem}_fast_{index}{source.suffix}")
        index += 1
    return candidate


class Mp3SpeedApp:
    def __init__(self, root: TkinterDnD.Tk):
        self.root = root
        self.root.title("MP3 变速工具")
        self.root.geometry("620x540")
        self.root.resizable(False, False)
        self.root.configure(bg="#1e1e2e")

        self.files: list[Path] = []
        self._build_ui()

    def _build_ui(self):
        # ── 样式 ──
        style = ttk.Style()
        style.theme_use("clam")

        style.configure("Title.TLabel", font=("Segoe UI", 16, "bold"),
                        foreground="#cdd6f4", background="#1e1e2e")
        style.configure("Sub.TLabel", font=("Segoe UI", 10),
                        foreground="#a6adc8", background="#1e1e2e")
        style.configure("Info.TLabel", font=("Segoe UI", 10),
                        foreground="#89b4fa", background="#1e1e2e")
        style.configure("TFrame", background="#1e1e2e")

        style.configure("Accent.TButton", font=("Segoe UI", 11, "bold"),
                        foreground="#1e1e2e", background="#89b4fa",
                        padding=(16, 8))
        style.map("Accent.TButton",
                  background=[("active", "#74c7ec"), ("disabled", "#585b70")])

        style.configure("File.TButton", font=("Segoe UI", 10),
                        foreground="#cdd6f4", background="#313244",
                        padding=(12, 6))
        style.map("File.TButton",
                  background=[("active", "#45475a")])

        style.configure("Custom.Horizontal.TScale", background="#1e1e2e",
                        troughcolor="#313244")

        # ── 标题 ──
        ttk.Label(self.root, text="🎵 MP3 变速工具", style="Title.TLabel").pack(pady=(20, 2))
        ttk.Label(self.root, text="变速不变调 · 基于 ffmpeg atempo", style="Sub.TLabel").pack()

        # ── 拖放区域 ──
        self.drop_frame = tk.Frame(
            self.root, bg="#313244", highlightbackground="#585b70",
            highlightthickness=2, cursor="hand2",
        )
        self.drop_frame.pack(pady=(16, 0), padx=30, fill="x", ipady=18)

        self.drop_label = tk.Label(
            self.drop_frame, text="📂  将 MP3 文件或文件夹拖放到这里",
            font=("Segoe UI", 11), fg="#a6adc8", bg="#313244",
        )
        self.drop_label.pack(expand=True)

        # 注册拖放
        self.drop_frame.drop_target_register(DND_FILES)
        self.drop_frame.dnd_bind("<<Drop>>", self._on_drop)
        self.drop_frame.dnd_bind("<<DragEnter>>", self._on_drag_enter)
        self.drop_frame.dnd_bind("<<DragLeave>>", self._on_drag_leave)
        # 让 label 也能接收拖放事件
        self.drop_label.drop_target_register(DND_FILES)
        self.drop_label.dnd_bind("<<Drop>>", self._on_drop)
        self.drop_label.dnd_bind("<<DragEnter>>", self._on_drag_enter)
        self.drop_label.dnd_bind("<<DragLeave>>", self._on_drag_leave)

        # ── 文件选择按钮 ──
        btn_frame = ttk.Frame(self.root)
        btn_frame.pack(pady=(10, 0), padx=30, fill="x")

        ttk.Button(btn_frame, text="📁 选择文件", style="File.TButton",
                   command=self._select_files).pack(side="left", padx=(0, 8))
        ttk.Button(btn_frame, text="📂 选择文件夹", style="File.TButton",
                   command=self._select_folder).pack(side="left")
        ttk.Button(btn_frame, text="🗑 清空", style="File.TButton",
                   command=self._clear_files).pack(side="right")

        self.file_label = ttk.Label(btn_frame, text="未选择文件", style="Info.TLabel")
        self.file_label.pack(side="right", padx=(0, 12))

        # ── 文件列表 ──
        list_frame = ttk.Frame(self.root)
        list_frame.pack(pady=(8, 0), padx=30, fill="both", expand=True)

        self.file_listbox = tk.Listbox(
            list_frame, height=6, font=("Consolas", 9),
            bg="#313244", fg="#cdd6f4", selectbackground="#585b70",
            selectforeground="#cdd6f4", borderwidth=0, highlightthickness=1,
            highlightcolor="#585b70", highlightbackground="#45475a",
        )
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.file_listbox.yview)
        self.file_listbox.configure(yscrollcommand=scrollbar.set)
        self.file_listbox.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # ── 速度调节 ──
        speed_frame = ttk.Frame(self.root)
        speed_frame.pack(pady=(12, 0), padx=30, fill="x")

        self.speed_var = tk.DoubleVar(value=1.05)
        self.speed_display = ttk.Label(speed_frame, text="播放速度: 1.05x", style="Info.TLabel")
        self.speed_display.pack(anchor="w")

        speed_scale = ttk.Scale(
            speed_frame, from_=0.5, to=2.0, orient="horizontal",
            variable=self.speed_var, command=self._on_speed_change,
            style="Custom.Horizontal.TScale",
        )
        speed_scale.pack(fill="x", pady=(4, 0))

        # 速度快捷按钮
        preset_frame = ttk.Frame(speed_frame)
        preset_frame.pack(fill="x", pady=(6, 0))
        for spd in [1.0, 1.05, 1.1, 1.25, 1.5, 2.0]:
            btn = tk.Button(
                preset_frame, text=f"{spd}x", font=("Segoe UI", 8),
                bg="#313244", fg="#cdd6f4", activebackground="#45475a",
                activeforeground="#cdd6f4", bd=0, padx=8, pady=2,
                command=lambda s=spd: self._set_speed(s),
            )
            btn.pack(side="left", padx=2)

        # ── 开始按钮 & 状态 ──
        bottom_frame = ttk.Frame(self.root)
        bottom_frame.pack(pady=(12, 20), padx=30, fill="x")

        self.start_btn = ttk.Button(
            bottom_frame, text="▶  开始处理", style="Accent.TButton",
            command=self._start_processing,
        )
        self.start_btn.pack(fill="x")

        self.status_label = ttk.Label(bottom_frame, text="", style="Sub.TLabel")
        self.status_label.pack(anchor="w", pady=(8, 0))

    # ── 拖放事件 ──

    def _parse_drop_data(self, data: str) -> list[str]:
        """使用 Tcl 自带解析器正确处理空格、花括号等路径字符。"""
        return list(self.root.tk.splitlist(data))

    def _on_drop(self, event):
        """处理拖放文件"""
        raw_paths = self._parse_drop_data(event.data)
        new_files: list[Path] = []

        for p_str in raw_paths:
            p = Path(p_str)
            if p.is_dir():
                new_files.extend(sorted(p.glob("*.mp3")))
            elif p.suffix.lower() == ".mp3" and p.is_file():
                new_files.append(p)

        if new_files:
            # 追加（去重）
            existing = {f.resolve() for f in self.files}
            for f in new_files:
                if f.resolve() not in existing:
                    self.files.append(f)
                    existing.add(f.resolve())
            self._refresh_file_list()

        self._on_drag_leave(None)

    def _on_drag_enter(self, _):
        self.drop_frame.configure(highlightbackground="#89b4fa", bg="#45475a")
        self.drop_label.configure(bg="#45475a", fg="#89b4fa",
                                  text="📥  松开以添加文件")

    def _on_drag_leave(self, _):
        self.drop_frame.configure(highlightbackground="#585b70", bg="#313244")
        self.drop_label.configure(bg="#313244", fg="#a6adc8",
                                  text="📂  将 MP3 文件或文件夹拖放到这里")

    # ── 文件操作 ──

    def _select_files(self):
        paths = filedialog.askopenfilenames(
            title="选择 MP3 文件",
            filetypes=[("MP3 文件", "*.mp3"), ("所有文件", "*.*")],
        )
        if paths:
            self.files = [Path(p) for p in paths]
            self._refresh_file_list()

    def _select_folder(self):
        folder = filedialog.askdirectory(title="选择包含 MP3 的文件夹")
        if folder:
            self.files = sorted(Path(folder).glob("*.mp3"))
            self._refresh_file_list()

    def _clear_files(self):
        self.files.clear()
        self._refresh_file_list()
        self.status_label.config(text="")

    def _refresh_file_list(self):
        self.file_listbox.delete(0, tk.END)
        for f in self.files:
            self.file_listbox.insert(tk.END, f"  {f.name}")
        count = len(self.files)
        self.file_label.config(text=f"已选择 {count} 个文件" if count else "未选择文件")

    # ── 速度 ──

    def _on_speed_change(self, _=None):
        val = round(self.speed_var.get(), 2)
        self.speed_display.config(text=f"播放速度: {val}x")

    def _set_speed(self, speed: float):
        self.speed_var.set(speed)
        self._on_speed_change()

    # ── 处理 ──

    def _start_processing(self):
        if not self.files:
            self.status_label.config(text="⚠️ 请先选择或拖入文件", foreground="#f38ba8")
            return
        if shutil.which("ffmpeg") is None:
            messagebox.showerror("未找到 FFmpeg", "请安装 FFmpeg 并将其加入 PATH。")
            return

        files = tuple(self.files)
        speed = round(self.speed_var.get(), 2)
        self.start_btn.config(state="disabled")
        threading.Thread(
            target=self._process_files, args=(files, speed), daemon=True
        ).start()

    def _process_files(self, files: tuple[Path, ...], speed: float):
        total = len(files)
        success = 0
        errors = []

        for i, mp3 in enumerate(files, 1):
            self._update_status(f"⏳ [{i}/{total}] 处理中: {mp3.name}")
            if not mp3.is_file():
                errors.append(f"{mp3.name}：文件不存在")
                continue
            output = available_output_path(mp3)

            cmd = [
                "ffmpeg", "-y",
                "-i", str(mp3),
                "-filter:a", f"atempo={speed}",
                "-vn",
                str(output),
            ]
            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    creationflags=CREATE_NO_WINDOW,
                )
                if result.returncode == 0:
                    success += 1
                else:
                    detail = result.stderr.strip().splitlines()
                    errors.append(f"{mp3.name}：{detail[-1] if detail else '转换失败'}")
            except FileNotFoundError:
                errors.append("未找到 FFmpeg")
                break

        self.root.after(0, self._processing_finished, success, total, errors)

    def _processing_finished(self, success: int, total: int, errors: list[str]):
        self.start_btn.config(state="normal")
        self.status_label.config(
            text=f"完成：成功 {success}/{total} 个文件", foreground="#a6adc8"
        )
        if errors:
            messagebox.showwarning(
                "处理完成",
                f"成功 {success}/{total} 个文件。\n\n失败详情：\n" + "\n".join(errors[:8]),
            )

    def _update_status(self, text: str):
        self.root.after(0, lambda: self.status_label.config(text=text, foreground="#a6adc8"))


if __name__ == "__main__":
    app = TkinterDnD.Tk()
    Mp3SpeedApp(app)
    app.mainloop()
