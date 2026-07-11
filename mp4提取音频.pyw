"""使用 FFmpeg 从视频中提取 MP3 音频。"""

import re
import shutil
import subprocess
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Optional


CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
TIME_PATTERN = re.compile(r"(\d+):(\d+):(\d+(?:\.\d+)?)")


def time_to_seconds(value: str) -> float:
    """将 FFmpeg 时间格式转换为秒。"""
    match = TIME_PATTERN.fullmatch(value.strip())
    if not match:
        return 0.0
    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def probe_duration(file_path: Path) -> float:
    """使用 ffprobe 获取媒体时长。"""
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(file_path),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=CREATE_NO_WINDOW,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "ffprobe 无法读取媒体信息")
    try:
        return float(result.stdout.strip())
    except ValueError as error:
        raise RuntimeError("ffprobe 返回了无效时长") from error


class MP4ToMP3Converter:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("视频音频提取器")
        self.root.geometry("520x390")
        self.root.resizable(False, False)
        self.process: Optional[subprocess.Popen[str]] = None
        self.cancel_requested = threading.Event()
        self._build_ui()

        if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
            self.convert_button.config(state="disabled")
            self.root.after(
                100,
                lambda: messagebox.showerror(
                    "缺少组件", "未找到 FFmpeg 或 ffprobe，请安装并加入 PATH。"
                ),
            )

    def _build_ui(self) -> None:
        tk.Label(self.root, text="选择视频文件:").grid(
            row=0, column=0, padx=10, pady=(15, 5), sticky="w"
        )
        self.input_entry = tk.Entry(self.root, width=52)
        self.input_entry.grid(row=1, column=0, padx=10, pady=5)
        self.input_button = tk.Button(self.root, text="浏览", command=self.select_input_file)
        self.input_button.grid(row=1, column=1, padx=10, pady=5)

        tk.Label(self.root, text="保存 MP3 文件位置:").grid(
            row=2, column=0, padx=10, pady=(10, 5), sticky="w"
        )
        self.output_entry = tk.Entry(self.root, width=52)
        self.output_entry.grid(row=3, column=0, padx=10, pady=5)
        self.output_button = tk.Button(self.root, text="浏览", command=self.select_output_file)
        self.output_button.grid(row=3, column=1, padx=10, pady=5)

        tk.Label(self.root, text="音频质量:").grid(
            row=4, column=0, padx=10, pady=(10, 5), sticky="w"
        )
        self.quality_var = tk.StringVar(value="192k")
        quality_frame = tk.Frame(self.root)
        quality_frame.grid(row=5, column=0, columnspan=2, padx=10, sticky="w")
        for text, value in (
            ("高质量 (320k)", "320k"),
            ("标准 (192k)", "192k"),
            ("压缩 (128k)", "128k"),
        ):
            tk.Radiobutton(
                quality_frame, text=text, variable=self.quality_var, value=value
            ).pack(side=tk.LEFT, padx=(0, 12))

        self.convert_button = tk.Button(
            self.root,
            text="开始提取",
            command=self.start_conversion,
            bg="#4CAF50",
            fg="white",
        )
        self.convert_button.grid(row=6, column=0, columnspan=2, pady=18)

        self.progress_var = tk.DoubleVar()
        ttk.Progressbar(
            self.root, variable=self.progress_var, maximum=100
        ).grid(row=7, column=0, columnspan=2, padx=10, sticky="ew")
        self.status_label = tk.Label(self.root, text="准备就绪", fg="green")
        self.status_label.grid(row=8, column=0, columnspan=2, pady=8)
        self.cancel_button = tk.Button(
            self.root,
            text="取消转换",
            command=self.cancel_conversion,
            state="disabled",
        )
        self.cancel_button.grid(row=9, column=0, columnspan=2)

    def select_input_file(self) -> None:
        input_file = filedialog.askopenfilename(
            title="选择视频文件",
            filetypes=[
                ("视频文件", "*.mp4 *.avi *.mkv *.mov *.wmv *.flv *.webm"),
                ("所有文件", "*.*"),
            ],
        )
        if not input_file:
            return
        input_path = Path(input_file)
        self._set_entry(self.input_entry, input_file)
        self._set_entry(self.output_entry, str(input_path.with_suffix(".mp3")))
        self.status_label.config(text="已选择输入文件", fg="blue")

    def select_output_file(self) -> None:
        output_file = filedialog.asksaveasfilename(
            title="保存 MP3 文件",
            filetypes=[("MP3 文件", "*.mp3")],
            defaultextension=".mp3",
        )
        if output_file:
            self._set_entry(self.output_entry, output_file)

    @staticmethod
    def _set_entry(entry: tk.Entry, value: str) -> None:
        entry.delete(0, tk.END)
        entry.insert(0, value)

    def start_conversion(self) -> None:
        input_text = self.input_entry.get().strip()
        output_text = self.output_entry.get().strip()
        if not input_text or not output_text:
            messagebox.showerror("错误", "请选择输入文件和输出文件位置。")
            return
        input_path = Path(input_text)
        output_path = Path(output_text)
        if not input_path.is_file():
            messagebox.showerror("错误", "输入文件不存在或不是文件。")
            return
        if input_path.resolve() == output_path.resolve():
            messagebox.showerror("错误", "输入和输出文件不能相同。")
            return
        if output_path.exists() and not messagebox.askyesno("确认覆盖", "输出文件已存在，是否覆盖？"):
            return

        self.cancel_requested.clear()
        self._set_busy(True)
        threading.Thread(
            target=self._convert,
            args=(input_path, output_path, self.quality_var.get()),
            daemon=True,
        ).start()

    def _convert(self, input_path: Path, output_path: Path, quality: str) -> None:
        error_message = None
        cancelled = False
        try:
            duration = probe_duration(input_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            command = [
                "ffmpeg",
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                str(input_path),
                "-vn",
                "-c:a",
                "libmp3lame",
                "-b:a",
                quality,
                "-progress",
                "pipe:1",
                "-nostats",
                str(output_path),
            ]
            self.process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=CREATE_NO_WINDOW,
            )
            assert self.process.stdout is not None
            for line in self.process.stdout:
                if self.cancel_requested.is_set():
                    cancelled = True
                    self.process.terminate()
                    break
                if line.startswith("out_time=") and duration > 0:
                    progress = min(time_to_seconds(line.partition("=")[2]) / duration * 100, 100)
                    self.root.after(0, self._update_progress, progress)

            return_code = self.process.wait()
            if self.cancel_requested.is_set():
                cancelled = True
            elif return_code != 0:
                stderr = self.process.stderr.read().strip() if self.process.stderr else ""
                error_message = stderr.splitlines()[-1] if stderr else "FFmpeg 转换失败"
        except (OSError, RuntimeError) as error:
            error_message = str(error)
        finally:
            self.process = None

        if cancelled:
            try:
                output_path.unlink(missing_ok=True)
            except OSError:
                pass
        self.root.after(0, self._conversion_finished, output_path, cancelled, error_message)

    def _update_progress(self, progress: float) -> None:
        self.progress_var.set(progress)
        self.status_label.config(text=f"转换进度: {progress:.1f}%", fg="blue")

    def _conversion_finished(
        self, output_path: Path, cancelled: bool, error_message: Optional[str]
    ) -> None:
        self._set_busy(False)
        if cancelled:
            self.status_label.config(text="转换已取消", fg="orange")
        elif error_message:
            self.status_label.config(text="转换失败", fg="red")
            messagebox.showerror("转换失败", error_message)
        else:
            self.progress_var.set(100)
            self.status_label.config(text="转换完成", fg="green")
            messagebox.showinfo("成功", f"音频已保存到：\n{output_path}")

    def _set_busy(self, busy: bool) -> None:
        normal_state = tk.DISABLED if busy else tk.NORMAL
        self.input_button.config(state=normal_state)
        self.output_button.config(state=normal_state)
        self.convert_button.config(state=normal_state, text="提取中..." if busy else "开始提取")
        self.cancel_button.config(state=tk.NORMAL if busy else tk.DISABLED)
        if busy:
            self.progress_var.set(0)
            self.status_label.config(text="正在转换...", fg="blue")

    def cancel_conversion(self) -> None:
        self.cancel_requested.set()
        if self.process and self.process.poll() is None:
            self.process.terminate()
        self.status_label.config(text="正在取消...", fg="orange")


def main() -> None:
    root = tk.Tk()
    MP4ToMP3Converter(root)
    root.mainloop()


if __name__ == "__main__":
    main()
