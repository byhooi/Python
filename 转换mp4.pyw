"""基于 FFmpeg 的通用视频转 MP4 工具。"""

import json
import os
import shutil
import subprocess
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Optional, Tuple


CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def get_video_info(file_path: Path) -> Optional[Tuple[float, str]]:
    """获取视频时长和第一路视频流分辨率。"""
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "format=duration:stream=width,height",
            "-of",
            "json",
            str(file_path),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=CREATE_NO_WINDOW,
    )
    if result.returncode != 0:
        return None
    try:
        data = json.loads(result.stdout)
        duration = float(data.get("format", {}).get("duration", 0))
        stream = data.get("streams", [{}])[0]
        width, height = stream.get("width"), stream.get("height")
        resolution = f"{width}x{height}" if width and height else "未知"
        return duration, resolution
    except (ValueError, TypeError, KeyError, IndexError, json.JSONDecodeError):
        return None


def check_file_integrity(file_path: Path) -> bool:
    """检查源文件是否存在、非空且可读。"""
    try:
        return file_path.is_file() and file_path.stat().st_size > 0 and os.access(file_path, os.R_OK)
    except OSError:
        return False


def progress_time_to_seconds(value: str) -> float:
    """解析 FFmpeg progress 输出中的 HH:MM:SS.microseconds。"""
    try:
        hours, minutes, seconds = value.strip().split(":", 2)
        return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    except (ValueError, TypeError):
        return 0.0


class VideoConverterApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("视频转换器 v3.0")
        self.root.geometry("720x510")
        self.root.minsize(680, 480)
        self.process: Optional[subprocess.Popen[str]] = None
        self.cancel_requested = threading.Event()
        self.source_file_path = tk.StringVar()
        self.target_file_path = tk.StringVar()
        self.quality_var = tk.StringVar(value="中等质量")
        self.preset_var = tk.StringVar(value="中等")
        self.progress_var = tk.DoubleVar()
        self._build_ui()

        if not ffmpeg_available():
            self.convert_button.config(state="disabled")
            self.root.after(
                100,
                lambda: messagebox.showwarning(
                    "缺少组件", "未检测到 FFmpeg 或 ffprobe，请安装并加入 PATH。"
                ),
            )

    def _build_ui(self) -> None:
        main_frame = tk.Frame(self.root, padx=20, pady=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        file_frame = tk.LabelFrame(main_frame, text="文件选择", padx=10, pady=10)
        file_frame.pack(fill=tk.X, pady=(0, 15))
        file_frame.columnconfigure(1, weight=1)

        tk.Label(file_frame, text="源视频文件:").grid(row=0, column=0, sticky="w", pady=5)
        tk.Entry(file_frame, textvariable=self.source_file_path).grid(
            row=0, column=1, padx=5, pady=5, sticky="ew"
        )
        self.source_button = tk.Button(file_frame, text="选择文件", command=self.select_file)
        self.source_button.grid(row=0, column=2, padx=5)
        self.source_info_label = tk.Label(file_frame, text="请选择视频文件", fg="gray")
        self.source_info_label.grid(row=1, column=0, columnspan=3, sticky="w")

        tk.Label(file_frame, text="输出视频文件:").grid(row=2, column=0, sticky="w", pady=5)
        tk.Entry(file_frame, textvariable=self.target_file_path).grid(
            row=2, column=1, padx=5, pady=5, sticky="ew"
        )
        self.output_button = tk.Button(file_frame, text="保存位置", command=self.select_output_file)
        self.output_button.grid(row=2, column=2, padx=5)

        settings_frame = tk.LabelFrame(main_frame, text="转换设置", padx=10, pady=10)
        settings_frame.pack(fill=tk.X, pady=(0, 15))
        tk.Label(settings_frame, text="视频质量:").grid(row=0, column=0, sticky="w", pady=5)
        ttk.Combobox(
            settings_frame,
            textvariable=self.quality_var,
            values=["高质量", "中等质量", "低质量"],
            state="readonly",
            width=15,
        ).grid(row=0, column=1, padx=5, sticky="w")
        tk.Label(settings_frame, text="高质量文件更大", fg="gray").grid(
            row=0, column=2, padx=5, sticky="w"
        )

        tk.Label(settings_frame, text="编码速度:").grid(row=1, column=0, sticky="w", pady=5)
        ttk.Combobox(
            settings_frame,
            textvariable=self.preset_var,
            values=["快速", "中等", "慢速"],
            state="readonly",
            width=15,
        ).grid(row=1, column=1, padx=5, sticky="w")
        tk.Label(settings_frame, text="编码越慢，通常压缩率越高", fg="gray").grid(
            row=1, column=2, padx=5, sticky="w"
        )

        button_frame = tk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(0, 15))
        self.convert_button = tk.Button(
            button_frame,
            text="开始转换",
            command=self.convert_video,
            bg="#4CAF50",
            fg="white",
            width=15,
            height=2,
        )
        self.convert_button.pack(side=tk.LEFT, padx=5)
        self.cancel_button = tk.Button(
            button_frame,
            text="取消转换",
            command=self.cancel_conversion,
            state="disabled",
            width=15,
            height=2,
        )
        self.cancel_button.pack(side=tk.LEFT, padx=5)

        progress_frame = tk.LabelFrame(main_frame, text="转换进度", padx=10, pady=10)
        progress_frame.pack(fill=tk.X)
        ttk.Progressbar(progress_frame, variable=self.progress_var, maximum=100).pack(
            fill=tk.X, pady=5
        )
        self.progress_label = tk.Label(progress_frame, text="准备就绪", fg="blue")
        self.progress_label.pack(pady=5)

    def select_file(self) -> None:
        source = filedialog.askopenfilename(
            title="选择要转换的视频文件",
            filetypes=[
                ("视频文件", "*.avi *.mov *.mkv *.wmv *.flv *.mpeg *.mp4 *.webm"),
                ("所有文件", "*.*"),
            ],
        )
        if not source:
            return
        source_path = Path(source)
        self.source_file_path.set(source)
        self.target_file_path.set(str(source_path.with_name(f"{source_path.stem}_converted.mp4")))
        info = get_video_info(source_path)
        if info:
            duration, resolution = info
            self.source_info_label.config(
                text=f"时长: {duration:.1f} 秒，分辨率: {resolution}", fg="blue"
            )
        else:
            self.source_info_label.config(text="无法获取视频信息", fg="orange")

    def select_output_file(self) -> None:
        output = filedialog.asksaveasfilename(
            defaultextension=".mp4",
            title="选择输出视频文件",
            filetypes=[("MP4 文件", "*.mp4")],
        )
        if output:
            self.target_file_path.set(output)

    def convert_video(self) -> None:
        source_text = self.source_file_path.get().strip()
        target_text = self.target_file_path.get().strip()
        if not source_text or not target_text:
            messagebox.showerror("错误", "请选择源视频和输出路径。")
            return
        source = Path(source_text)
        target = Path(target_text)
        if not check_file_integrity(source):
            messagebox.showerror("错误", "源文件不存在、为空或无法读取。")
            return
        if source.resolve() == target.resolve():
            messagebox.showerror("错误", "输出文件不能与源文件相同。")
            return
        if target.exists() and not messagebox.askyesno("确认覆盖", "输出文件已存在，是否覆盖？"):
            return

        duration = get_video_info(source)
        total_duration = duration[0] if duration else 0.0
        crf = {"高质量": 20, "中等质量": 23, "低质量": 28}.get(
            self.quality_var.get(), 23
        )
        preset = {"快速": "fast", "中等": "medium", "慢速": "slow"}.get(
            self.preset_var.get(), "medium"
        )

        self.cancel_requested.clear()
        self._set_busy(True)
        threading.Thread(
            target=self._run_conversion,
            args=(source, target, total_duration, crf, preset),
            daemon=True,
        ).start()

    def _run_conversion(
        self, source: Path, target: Path, duration: float, crf: int, preset: str
    ) -> None:
        cancelled = False
        error_message = None
        full_error = ""
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            command = [
                "ffmpeg",
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                str(source),
                "-c:v",
                "libx264",
                "-tag:v",
                "avc1",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
                "-crf",
                str(crf),
                "-preset",
                preset,
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                "-progress",
                "pipe:1",
                "-nostats",
                str(target),
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
                    elapsed = progress_time_to_seconds(line.partition("=")[2])
                    self.root.after(0, self._update_progress, min(elapsed / duration * 100, 100))

            return_code = self.process.wait()
            full_error = self.process.stderr.read().strip() if self.process.stderr else ""
            if self.cancel_requested.is_set():
                cancelled = True
            elif return_code != 0:
                error_message = full_error.splitlines()[-1] if full_error else f"FFmpeg 错误码 {return_code}"
        except OSError as error:
            error_message = str(error)
        finally:
            self.process = None

        if cancelled:
            try:
                target.unlink(missing_ok=True)
            except OSError:
                pass
        elif error_message:
            try:
                log_path = target.with_name(f"{target.stem}_ffmpeg_error.log")
                log_path.write_text(full_error or error_message, encoding="utf-8")
                error_message = f"{error_message}\n\n错误日志：{log_path}"
            except OSError:
                pass

        self.root.after(0, self._conversion_finished, target, cancelled, error_message)

    def _update_progress(self, progress: float) -> None:
        self.progress_var.set(progress)
        self.progress_label.config(text=f"转换进度: {progress:.1f}%")

    def _conversion_finished(
        self, target: Path, cancelled: bool, error_message: Optional[str]
    ) -> None:
        self._set_busy(False)
        if cancelled:
            self.progress_label.config(text="转换已取消", fg="orange")
        elif error_message:
            self.progress_label.config(text="转换失败", fg="red")
            messagebox.showerror("转换失败", error_message)
        else:
            self.progress_var.set(100)
            self.progress_label.config(text="转换完成", fg="green")
            messagebox.showinfo("成功", f"视频已保存到：\n{target}")

    def _set_busy(self, busy: bool) -> None:
        state = tk.DISABLED if busy else tk.NORMAL
        self.source_button.config(state=state)
        self.output_button.config(state=state)
        self.convert_button.config(state=state, text="转换中..." if busy else "开始转换")
        self.cancel_button.config(state=tk.NORMAL if busy else tk.DISABLED)
        if busy:
            self.progress_var.set(0)
            self.progress_label.config(text="开始转换...", fg="blue")

    def cancel_conversion(self) -> None:
        self.cancel_requested.set()
        if self.process and self.process.poll() is None:
            self.process.terminate()
        self.progress_label.config(text="正在取消...", fg="orange")


def main() -> None:
    root = tk.Tk()
    VideoConverterApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
