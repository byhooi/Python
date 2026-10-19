#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全新听力.pyw — 教材音频批量转 MP3

配合 ecnupress.js v2.0.0+ 使用。浏览器只负责抓地址，下载、解密和编码
交给本地 ffmpeg。

双击本文件会打开图形界面，适合不熟悉命令行的使用者。
也可以在命令行中批量运行：

    python 全新听力.pyw ecnupress_episodes.json -o ./mp3

命令行参数：
    -o, --output        输出目录（默认 ./mp3）
    -b, --bitrate       MP3 比特率（默认 64k）
    -r, --sample-rate   输出采样率（默认 16000，与源音频一致）
    -j, --jobs          并行数（默认 4）
    -f, --force         覆盖已存在的输出文件

依赖：Python 3、tkinter（Python 自带）、ffmpeg 已安装。
"""

import argparse
import json
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox, scrolledtext
    HAS_TK = True
except Exception:
    HAS_TK = False

DEFAULT_BITRATE = "64k"
DEFAULT_SAMPLE_RATE = "16000"

# Windows 终端（Git Bash 等）中文输出兼容
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


# ----------------------------------------------------------------------
# 通用逻辑
# ----------------------------------------------------------------------

def sanitize(name, fallback):
    """清理文件名中的非法字符。"""
    name = re.sub(r'[\\/:*?"<>|\r\n\t]+', "_", name or "")
    name = re.sub(r"\s+", " ", name).strip(" .")
    return name[:80] or fallback


def find_ffmpeg():
    """返回 ffmpeg 路径，找不到时返回 None。"""
    return shutil.which("ffmpeg")


def convert_one(ffmpeg, input_spec, output_path, title, bitrate, sample_rate, force):
    """调用 ffmpeg 将单个输入（URL 或本地文件）转为 MP3。"""
    if not force and os.path.exists(output_path) and os.path.getsize(output_path) > 1024:
        return "skip"

    cmd = [
        ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
        "-i", input_spec,
        "-vn", "-ac", "1", "-ar", sample_rate,
        "-c:a", "libmp3lame", "-b:a", bitrate,
        "-id3v2_version", "3",
        "-metadata", f"title={title}",
        output_path,
    ]
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        # .pyw 由 pythonw 启动时没有控制台，需显式隐藏 ffmpeg 的子进程窗口
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if proc.returncode != 0:
        detail = (proc.stderr or "").strip().replace("\n", " ")
        raise RuntimeError(detail[-400:] or f"ffmpeg 退出码 {proc.returncode}")
    return "ok"


def load_episodes(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        data = data.get("episodes", [])
    if not isinstance(data, list):
        raise ValueError("清单格式不正确：缺少 episodes 数组")
    return data


def build_episode_jobs(episodes):
    """从清单构建 (序号, 标题, 输入) 列表。"""
    jobs = []
    for i, ep in enumerate(episodes, 1):
        if not isinstance(ep, dict):
            continue
        url = str(ep.get("url") or "").strip()
        if not url:
            continue
        index = ep.get("index") or i
        title = str(ep.get("title") or "")
        # 页面标题是 URL 或空时，交给序号命名
        if re.match(r"^https?://", title) or len(title) < 2:
            title = ""
        jobs.append((index, title, url))
    return jobs


def unique_name(name, used):
    """避免标题重复导致文件互相覆盖。"""
    if name.lower() not in used:
        used.add(name.lower())
        return name

    stem, ext = os.path.splitext(name)
    n = 2
    while f"{stem}_{n}{ext}".lower() in used:
        n += 1
    result = f"{stem}_{n}{ext}"
    used.add(result.lower())
    return result


def build_tasks(jobs, output_dir):
    """把任务列表转换为 (输入, 输出路径, 标题)。"""
    used_names = set()
    tasks = []
    for index, title, input_spec in jobs:
        try:
            number = int(index)
        except (TypeError, ValueError):
            number = len(tasks) + 1

        prefix = f"{number:03d}"
        safe_title = sanitize(title, f"第{prefix}集")
        # 输出文件名按单元编号：Unit 01.mp3、Unit 02.mp3……（补零保证字符排序正确）
        filename = f"Unit {number:02d}.mp3"
        filename = unique_name(filename, used_names)
        tasks.append((input_spec, os.path.join(output_dir, filename), safe_title))
    return tasks


# ----------------------------------------------------------------------
# 命令行模式
# ----------------------------------------------------------------------

def cli_main():
    parser = argparse.ArgumentParser(description="教材音频批量转 MP3")
    parser.add_argument("input", help="油猴脚本导出的 JSON 清单")
    parser.add_argument("-o", "--output", default="mp3", help="输出目录（默认 ./mp3）")
    parser.add_argument("-b", "--bitrate", default=DEFAULT_BITRATE, help="MP3 比特率（默认 64k）")
    parser.add_argument("-r", "--sample-rate", default=DEFAULT_SAMPLE_RATE, help="输出采样率（默认 16000）")
    parser.add_argument("-j", "--jobs", type=int, default=4, help="并行任务数（默认 4）")
    parser.add_argument("-f", "--force", action="store_true", help="覆盖已存在的输出文件")
    args = parser.parse_args()

    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        sys.exit("错误：未找到 ffmpeg，请先安装并加入 PATH")
    os.makedirs(args.output, exist_ok=True)

    if not os.path.exists(args.input):
        sys.exit(f"错误：找不到 {args.input}")
    jobs = build_episode_jobs(load_episodes(args.input))
    source_label = "清单"

    if not jobs:
        sys.exit("错误：没有可处理的音频")

    print(f"输入：{source_label}，共 {len(jobs)} 集，并行 {args.jobs}，输出到 {args.output}")

    tasks = build_tasks(jobs, args.output)
    ok = skipped = failed = 0
    failures = []

    with ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
        futures = {
            pool.submit(
                convert_one, ffmpeg, input_spec, output_path, title,
                args.bitrate, args.sample_rate, args.force,
            ): (title, output_path)
            for input_spec, output_path, title in tasks
        }

        for future in as_completed(futures):
            title, output_path = futures[future]
            try:
                status = future.result()
                if status == "skip":
                    skipped += 1
                    print(f"[跳过] {os.path.basename(output_path)}")
                else:
                    ok += 1
                    print(f"[完成] {os.path.basename(output_path)}")
            except Exception as exc:
                failed += 1
                failures.append((os.path.basename(output_path), str(exc)))
                print(f"[失败] {os.path.basename(output_path)}: {exc}")

    print(f"\n完成：成功 {ok}，跳过 {skipped}，失败 {failed}")
    if failures:
        print("失败详情：")
        for name, err in failures:
            print(f"  - {name}: {err}")
        return 1
    return 0


# ----------------------------------------------------------------------
# 图形界面模式
# ----------------------------------------------------------------------

if HAS_TK:
    class BatchApp:
        def __init__(self, root):
            self.root = root
            self.root.title("全新听力 · 音频批量转 MP3")
            self.root.geometry("780x640")
            self.root.minsize(700, 580)

            self.queue = queue.Queue()
            self.worker = None
            self.cancel_event = threading.Event()
            self.done_shown = False

            self.input_var = tk.StringVar()
            self.output_var = tk.StringVar()
            self.bitrate_var = tk.StringVar(value=DEFAULT_BITRATE)
            self.samplerate_var = tk.StringVar(value=DEFAULT_SAMPLE_RATE)
            self.jobs_var = tk.IntVar(value=4)
            self.ffmpeg_var = tk.StringVar(value=find_ffmpeg() or "")
            self.status_var = tk.StringVar(value="请选择清单文件")

            self._build_ui()
            self.root.report_callback_exception = self._report_error

        # ---------------- 界面 ----------------

        def _build_ui(self):
            main = ttk.Frame(self.root, padding=12)
            main.pack(fill="both", expand=True)
            main.columnconfigure(0, weight=1)

            # 1. 输入
            input_frame = ttk.LabelFrame(main, text="1. 选择要转换的内容", padding=8)
            input_frame.grid(row=0, column=0, sticky="ew", pady=(0, 8))
            input_frame.columnconfigure(0, weight=1)

            ttk.Entry(input_frame, textvariable=self.input_var).grid(
                row=0, column=0, sticky="ew", padx=(0, 6)
            )
            ttk.Button(input_frame, text="选择清单文件…", command=self.pick_manifest).grid(
                row=0, column=1, padx=2
            )
            ttk.Label(
                input_frame,
                foreground="#666",
                text="在教材页面点「导出清单」得到的 ecnupress_episodes.json",
            ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(6, 0))

            # 2. 输出设置
            opt_frame = ttk.LabelFrame(main, text="2. 输出设置", padding=8)
            opt_frame.grid(row=1, column=0, sticky="ew", pady=(0, 8))
            opt_frame.columnconfigure(1, weight=1)

            ttk.Label(opt_frame, text="输出目录：").grid(row=0, column=0, sticky="w")
            ttk.Entry(opt_frame, textvariable=self.output_var).grid(
                row=0, column=1, sticky="ew", padx=6
            )
            ttk.Button(opt_frame, text="浏览…", command=self.pick_output).grid(row=0, column=2)

            params = ttk.Frame(opt_frame)
            params.grid(row=1, column=0, columnspan=3, sticky="w", pady=(8, 0))
            ttk.Label(params, text="比特率：").pack(side="left")
            ttk.Combobox(
                params, textvariable=self.bitrate_var,
                values=["32k", "48k", "64k", "96k", "128k"],
                width=7, state="readonly",
            ).pack(side="left", padx=(0, 16))
            ttk.Label(params, text="采样率：").pack(side="left")
            ttk.Combobox(
                params, textvariable=self.samplerate_var,
                values=["16000", "22050", "44100", "48000"],
                width=8, state="readonly",
            ).pack(side="left", padx=(0, 16))
            ttk.Label(params, text="并行数：").pack(side="left")
            ttk.Spinbox(params, from_=1, to=8, textvariable=self.jobs_var, width=4).pack(side="left")

            ttk.Label(
                opt_frame,
                foreground="#666",
                text="默认 64k / 16000 Hz 单声道，适合倾听者等语音播放器",
            ).grid(row=2, column=0, columnspan=3, sticky="w", pady=(6, 0))

            # 3. ffmpeg
            ff_frame = ttk.LabelFrame(main, text="3. ffmpeg", padding=8)
            ff_frame.grid(row=2, column=0, sticky="ew", pady=(0, 8))
            ff_frame.columnconfigure(0, weight=1)

            ttk.Entry(ff_frame, textvariable=self.ffmpeg_var).grid(
                row=0, column=0, sticky="ew", padx=(0, 6)
            )
            ttk.Button(ff_frame, text="浏览…", command=self.pick_ffmpeg).grid(row=0, column=1)
            self.ffmpeg_hint = ttk.Label(ff_frame, foreground="#666", text="")
            self.ffmpeg_hint.grid(row=1, column=0, columnspan=2, sticky="w", pady=(6, 0))
            self._refresh_ffmpeg_hint()

            # 4. 操作
            action = ttk.Frame(main)
            action.grid(row=3, column=0, sticky="ew", pady=(0, 8))
            action.columnconfigure(2, weight=1)

            self.start_btn = ttk.Button(action, text="开始转换", command=self.start)
            self.start_btn.grid(row=0, column=0, padx=(0, 6))
            self.cancel_btn = ttk.Button(action, text="取消", command=self.cancel, state="disabled")
            self.cancel_btn.grid(row=0, column=1, padx=(0, 12))
            self.progress = ttk.Progressbar(action, mode="determinate")
            self.progress.grid(row=0, column=2, sticky="ew")

            ttk.Label(main, textvariable=self.status_var).grid(
                row=4, column=0, sticky="w", pady=(0, 6)
            )

            # 5. 日志
            self.log = scrolledtext.ScrolledText(main, height=12, state="disabled", wrap="word")
            self.log.grid(row=5, column=0, sticky="nsew")
            main.rowconfigure(5, weight=1)

            ttk.Label(
                main,
                foreground="#888",
                text="提示：转换期间可以继续使用电脑；关闭窗口不会中断已经开始的 ffmpeg 任务。",
            ).grid(row=6, column=0, sticky="w", pady=(6, 0))

        # ---------------- 选择文件 ----------------

        def pick_manifest(self):
            path = filedialog.askopenfilename(
                title="选择清单文件",
                filetypes=[("清单文件", "*.json"), ("所有文件", "*.*")],
            )
            if not path:
                return
            self.input_var.set(path)
            if not self.output_var.get().strip():
                self.output_var.set(os.path.join(os.path.dirname(path), "mp3"))
            try:
                count = len(build_episode_jobs(load_episodes(path)))
                self.status_var.set(f"已读取清单：{count} 集")
                self.log_line(f"已读取清单：{path}（{count} 集）")
            except Exception as exc:
                messagebox.showerror("读取失败", f"无法读取清单：\n{exc}")

        def pick_output(self):
            initial = self.output_var.get().strip()
            kwargs = {"title": "选择输出目录"}
            if initial and os.path.isdir(initial):
                kwargs["initialdir"] = initial
            path = filedialog.askdirectory(**kwargs)
            if path:
                self.output_var.set(path)

        def pick_ffmpeg(self):
            path = filedialog.askopenfilename(
                title="选择 ffmpeg.exe",
                filetypes=[("ffmpeg", "ffmpeg.exe"), ("可执行文件", "*.exe"), ("所有文件", "*.*")],
            )
            if path:
                self.ffmpeg_var.set(path)
                self._refresh_ffmpeg_hint()

        def _refresh_ffmpeg_hint(self):
            path = self.ffmpeg_var.get().strip()
            if path and os.path.exists(path):
                self.ffmpeg_hint.config(text="已找到 ffmpeg：" + path)
            else:
                self.ffmpeg_hint.config(
                    text="未检测到 ffmpeg，请点击「浏览…」选择 ffmpeg.exe，或安装后加入 PATH"
                )

        # ---------------- 转换流程 ----------------

        def start(self):
            if self.worker and self.worker.is_alive():
                return

            input_path = self.input_var.get().strip()
            output_dir = self.output_var.get().strip()
            ffmpeg = self.ffmpeg_var.get().strip()

            if not input_path:
                messagebox.showwarning("缺少输入", "请先选择清单文件")
                return
            if not os.path.exists(input_path):
                messagebox.showerror("找不到输入", f"路径不存在：\n{input_path}")
                return
            if not ffmpeg or not os.path.exists(ffmpeg):
                messagebox.showerror(
                    "缺少 ffmpeg",
                    "未找到 ffmpeg。\n请点击「浏览…」选择 ffmpeg.exe，或安装 ffmpeg 并加入 PATH。",
                )
                return

            if not output_dir:
                output_dir = os.path.join(os.getcwd(), "mp3")
                self.output_var.set(output_dir)

            try:
                os.makedirs(output_dir, exist_ok=True)
            except Exception as exc:
                messagebox.showerror("无法创建输出目录", str(exc))
                return

            try:
                jobs = build_episode_jobs(load_episodes(input_path))
            except Exception as exc:
                messagebox.showerror("读取失败", str(exc))
                return

            if not jobs:
                messagebox.showwarning("没有音频", "没有找到可转换的音频。")
                return

            tasks = build_tasks(jobs, output_dir)

            self.cancel_event.clear()
            self.done_shown = False
            self._clear_log()
            self.progress.config(value=0, maximum=len(tasks))
            self.status_var.set(f"正在准备：共 {len(tasks)} 集")
            self._set_running(True)

            self.worker = threading.Thread(
                target=self._run,
                args=(ffmpeg, tasks, output_dir),
                daemon=True,
            )
            self.worker.start()
            self.root.after(100, self._poll)

        def cancel(self):
            if self.worker and self.worker.is_alive():
                self.cancel_event.set()
                self.status_var.set("正在取消…（已开始的 ffmpeg 任务会执行完）")
                self.log_line("已请求取消，不会再开始新任务")

        def _run(self, ffmpeg, tasks, output_dir):
            try:
                jobs = max(1, int(self.jobs_var.get()))
            except Exception:
                jobs = 4
            bitrate = self.bitrate_var.get()
            sample_rate = self.samplerate_var.get()

            ok = skipped = failed = 0
            failures = []
            done = 0
            total = len(tasks)

            self.queue.put(("log", f"开始处理 {total} 集（并行 {jobs}，{bitrate} / {sample_rate} Hz）"))

            with ThreadPoolExecutor(max_workers=jobs) as pool:
                futures = {}
                for input_spec, output_path, title in tasks:
                    if self.cancel_event.is_set():
                        break
                    future = pool.submit(
                        convert_one, ffmpeg, input_spec, output_path, title,
                        bitrate, sample_rate, False,
                    )
                    futures[future] = output_path

                for future in as_completed(futures):
                    output_path = futures[future]
                    name = os.path.basename(output_path)
                    try:
                        status = future.result()
                        if status == "skip":
                            skipped += 1
                            self.queue.put(("log", f"[跳过] {name}"))
                        else:
                            ok += 1
                            self.queue.put(("log", f"[完成] {name}"))
                    except Exception as exc:
                        failed += 1
                        failures.append((name, str(exc)))
                        self.queue.put(("log", f"[失败] {name}: {exc}"))
                    done += 1
                    self.queue.put(("progress", done, total))

            self.queue.put(
                ("done", ok, skipped, failed, failures, output_dir, self.cancel_event.is_set())
            )

        def _poll(self):
            while True:
                try:
                    message = self.queue.get_nowait()
                except queue.Empty:
                    break
                self._handle_message(message)
            if self.worker and self.worker.is_alive():
                self.root.after(100, self._poll)

        def _handle_message(self, message):
            kind = message[0]

            if kind == "log":
                self.log_line(message[1])
                return

            if kind == "progress":
                done, total = message[1], message[2]
                self.progress.config(value=done, maximum=total)
                self.status_var.set(f"正在转换：{done}/{total}")
                return

            if kind == "done":
                ok, skipped, failed, failures, output_dir, cancelled = message[1:]
                self._set_running(False)
                summary = f"成功 {ok}，跳过 {skipped}，失败 {failed}"
                if cancelled:
                    self.status_var.set("已取消：" + summary)
                else:
                    self.status_var.set("完成：" + summary)
                self.log_line(self.status_var.get())

                if self.done_shown:
                    return
                self.done_shown = True

                if failures:
                    detail = "\n".join(f"{name}: {err}" for name, err in failures[:5])
                    messagebox.showwarning(
                        "转换完成（有失败）",
                        f"{self.status_var.get()}\n\n{detail}",
                    )
                elif not cancelled:
                    if messagebox.askyesno(
                        "转换完成",
                        f"{self.status_var.get()}\n\n是否打开输出目录？",
                    ):
                        self._open_directory(output_dir)

        # ---------------- 辅助 ----------------

        def _set_running(self, running):
            self.start_btn.config(state="disabled" if running else "normal")
            self.cancel_btn.config(state="normal" if running else "disabled")

        def log_line(self, text):
            self.log.config(state="normal")
            self.log.insert("end", text + "\n")
            self.log.see("end")
            self.log.config(state="disabled")

        def _clear_log(self):
            self.log.config(state="normal")
            self.log.delete("1.0", "end")
            self.log.config(state="disabled")

        def _open_directory(self, path):
            try:
                if sys.platform == "win32":
                    os.startfile(path)
                elif sys.platform == "darwin":
                    subprocess.Popen(["open", path])
                else:
                    subprocess.Popen(["xdg-open", path])
            except Exception:
                pass

        def _report_error(self, exc, value, traceback):
            messagebox.showerror("程序出错", f"{exc.__name__}: {value}")


def gui_main():
    if not HAS_TK:
        # 没有 GUI 环境时退回命令行提示
        print("当前环境不支持 tkinter 图形界面。")
        print("请使用命令行模式：python 全新听力.pyw <清单或目录> -o <输出目录>")
        return 1

    if sys.platform == "win32":
        try:
            from ctypes import windll
            windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass

    root = tk.Tk()
    BatchApp(root)

    # 窗口居中
    root.update_idletasks()
    width, height = 780, 640
    screen_w = root.winfo_screenwidth()
    screen_h = root.winfo_screenheight()
    x = max(0, (screen_w - width) // 2)
    y = max(0, (screen_h - height) // 3)
    root.geometry(f"{width}x{height}+{x}+{y}")

    root.mainloop()
    return 0


if __name__ == "__main__":
    # 有参数走命令行，双击（无参数）打开图形界面
    if len(sys.argv) > 1:
        sys.exit(cli_main())
    sys.exit(gui_main())
