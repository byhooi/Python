"""批量将常见音频格式转换为 MP3。"""

import os
import shutil
import subprocess
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Iterable, List


AUDIO_PATTERNS = "*.m4a *.wav *.flac *.wma *.aac *.ogg *.opus"
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def available_output_path(input_path: Path) -> Path:
    """生成不会覆盖现有文件的 MP3 输出路径。"""
    candidate = input_path.with_suffix(".mp3")
    if candidate != input_path and not candidate.exists():
        return candidate

    candidate = input_path.with_name(f"{input_path.stem}_converted.mp3")
    index = 2
    while candidate.exists():
        candidate = input_path.with_name(f"{input_path.stem}_converted_{index}.mp3")
        index += 1
    return candidate


class AudioConverterApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("音频批量转 MP3")
        self.root.geometry("680x430")
        self.root.minsize(560, 360)
        self.files: List[Path] = []
        self._build_ui()

    def _build_ui(self) -> None:
        top_frame = tk.Frame(self.root, pady=10)
        top_frame.pack(fill=tk.X, padx=10)

        self.add_button = tk.Button(top_frame, text="添加文件", command=self.add_files)
        self.add_button.pack(side=tk.LEFT, padx=5)
        self.remove_button = tk.Button(
            top_frame, text="移除选中", command=self.remove_selected
        )
        self.remove_button.pack(side=tk.LEFT, padx=5)
        self.clear_button = tk.Button(top_frame, text="清空列表", command=self.clear_list)
        self.clear_button.pack(side=tk.LEFT, padx=5)
        self.convert_button = tk.Button(
            top_frame,
            text="开始转换",
            command=self.start_conversion,
            bg="#4CAF50",
            fg="white",
            padx=12,
        )
        self.convert_button.pack(side=tk.RIGHT, padx=5)

        list_frame = tk.Frame(self.root)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.file_listbox = tk.Listbox(
            list_frame,
            yscrollcommand=scrollbar.set,
            selectmode=tk.EXTENDED,
        )
        self.file_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.file_listbox.yview)

        self.status_var = tk.StringVar(value="准备就绪")
        tk.Label(
            self.root,
            textvariable=self.status_var,
            bd=1,
            relief=tk.SUNKEN,
            anchor=tk.W,
        ).pack(side=tk.BOTTOM, fill=tk.X)

    def add_files(self) -> None:
        filenames = filedialog.askopenfilenames(
            title="选择音频文件",
            filetypes=[("音频文件", AUDIO_PATTERNS), ("所有文件", "*.*")],
        )
        if not filenames:
            return

        existing = {path.resolve() for path in self.files}
        added = 0
        for filename in filenames:
            path = Path(filename)
            resolved = path.resolve()
            if resolved not in existing:
                self.files.append(path)
                existing.add(resolved)
                added += 1
        self._refresh_list()
        self.status_var.set(f"新增 {added} 个文件，共 {len(self.files)} 个")

    def remove_selected(self) -> None:
        selected = set(self.file_listbox.curselection())
        if selected:
            self.files = [path for index, path in enumerate(self.files) if index not in selected]
            self._refresh_list()

    def clear_list(self) -> None:
        self.files.clear()
        self._refresh_list()
        self.status_var.set("列表已清空")

    def _refresh_list(self) -> None:
        self.file_listbox.delete(0, tk.END)
        for path in self.files:
            self.file_listbox.insert(tk.END, str(path))

    def _set_busy(self, busy: bool) -> None:
        state = tk.DISABLED if busy else tk.NORMAL
        self.add_button.config(state=state)
        self.remove_button.config(state=state)
        self.clear_button.config(state=state)
        self.convert_button.config(state=state)

    def start_conversion(self) -> None:
        if not self.files:
            messagebox.showwarning("没有文件", "请先添加需要转换的音频文件。")
            return
        if shutil.which("ffmpeg") is None:
            messagebox.showerror("未找到 FFmpeg", "请安装 FFmpeg 并将其加入 PATH。")
            return

        files = tuple(self.files)
        self._set_busy(True)
        threading.Thread(target=self._convert_files, args=(files,), daemon=True).start()

    def _convert_files(self, files: Iterable[Path]) -> None:
        file_list = list(files)
        errors = []
        success_count = 0

        for index, input_path in enumerate(file_list, 1):
            self.root.after(
                0,
                self.status_var.set,
                f"正在转换 ({index}/{len(file_list)}): {input_path.name}",
            )
            if not input_path.is_file():
                errors.append(f"{input_path.name}：文件不存在")
                continue

            output_path = available_output_path(input_path)
            command = [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                str(input_path),
                "-vn",
                "-c:a",
                "libmp3lame",
                "-q:a",
                "2",
                str(output_path),
            ]
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=CREATE_NO_WINDOW,
            )
            if result.returncode == 0:
                success_count += 1
            else:
                detail = result.stderr.strip().splitlines()
                errors.append(
                    f"{input_path.name}：{detail[-1] if detail else 'FFmpeg 转换失败'}"
                )

        self.root.after(0, self._conversion_finished, success_count, len(file_list), errors)

    def _conversion_finished(self, success: int, total: int, errors: List[str]) -> None:
        self._set_busy(False)
        self.status_var.set(f"转换完成：成功 {success}/{total}")
        if errors:
            messagebox.showwarning(
                "转换完成",
                f"成功 {success}/{total} 个文件。\n\n失败详情：\n" + "\n".join(errors[:8]),
            )
        else:
            messagebox.showinfo("转换完成", f"已成功转换 {success} 个文件。")


def main() -> None:
    root = tk.Tk()
    AudioConverterApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
