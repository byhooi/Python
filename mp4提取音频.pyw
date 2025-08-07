import os
import shutil
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import subprocess
import threading
from typing import Optional
from pathlib import Path

class MP4ToMP3Converter:
    def __init__(self, root):
        self.root = root
        self.root.title("MP4 到 MP3 转换器")
        self.root.geometry("450x350")  # 增大窗口以容纳新控件
        self.root.resizable(False, False)
        
        # 检查FFmpeg是否可用
        if not self.check_ffmpeg():
            messagebox.showerror("错误", "未找到FFmpeg！请确保FFmpeg已安装并在PATH中。")
            self.root.quit()
            return
        
        # 输入文件标签和按钮
        self.input_label = tk.Label(root, text="选择 MP4 文件:")
        self.input_label.grid(row=0, column=0, padx=10, pady=10, sticky="w")
        self.input_entry = tk.Entry(root, width=40)
        self.input_entry.grid(row=1, column=0, padx=10, pady=5)
        self.input_button = tk.Button(root, text="浏览", command=self.select_input_file)
        self.input_button.grid(row=1, column=1, padx=10, pady=5)

        # 输出文件标签和按钮
        self.output_label = tk.Label(root, text="保存 MP3 文件位置:")
        self.output_label.grid(row=2, column=0, padx=10, pady=10, sticky="w")
        self.output_entry = tk.Entry(root, width=40)
        self.output_entry.grid(row=3, column=0, padx=10, pady=5)
        self.output_button = tk.Button(root, text="浏览", command=self.select_output_file)
        self.output_button.grid(row=3, column=1, padx=10, pady=5)

        # 音频质量选择
        self.quality_label = tk.Label(root, text="音频质量:")
        self.quality_label.grid(row=4, column=0, padx=10, pady=5, sticky="w")
        self.quality_var = tk.StringVar(value="192k")
        quality_frame = tk.Frame(root)
        quality_frame.grid(row=4, column=1, padx=10, pady=5, sticky="w")
        
        qualities = [("高质量 (320k)", "320k"), ("标准 (192k)", "192k"), ("压缩 (128k)", "128k")]
        for text, value in qualities:
            tk.Radiobutton(quality_frame, text=text, variable=self.quality_var, 
                          value=value).pack(anchor="w")
        
        # 转换按钮
        self.convert_button = tk.Button(root, text="转换", command=self.start_conversion_thread, 
                                      bg="#4CAF50", fg="white", font=("Arial", 10, "bold"))
        self.convert_button.grid(row=5, column=0, columnspan=2, pady=20)

        # 进度条
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(root, variable=self.progress_var, maximum=100)
        self.progress_bar.grid(row=6, column=0, columnspan=2, padx=10, pady=10, sticky="ew")

        # 状态标签
        self.status_label = tk.Label(root, text="准备就绪", fg="green")
        self.status_label.grid(row=7, column=0, columnspan=2)
        
        # 取消按钮（初始隐藏）
        self.cancel_button = tk.Button(root, text="取消转换", command=self.cancel_conversion,
                                     bg="#f44336", fg="white", state="disabled")
        self.cancel_button.grid(row=8, column=0, columnspan=2, pady=5)
        
        self.conversion_process: Optional[subprocess.Popen] = None

    def check_ffmpeg(self) -> bool:
        """检查FFmpeg是否可用"""
        return shutil.which("ffmpeg") is not None
    
    def select_input_file(self):
        filetypes = [
            ("视频文件", "*.mp4;*.avi;*.mkv;*.mov;*.wmv;*.flv"),
            ("MP4文件", "*.mp4"),
            ("所有文件", "*.*")
        ]
        input_file = filedialog.askopenfilename(title="选择视频文件", filetypes=filetypes)
        if input_file:
            self.input_entry.delete(0, tk.END)
            self.input_entry.insert(0, input_file)

            # 自动设置 MP3 输出文件的默认路径
            input_path = Path(input_file)
            default_output_file = input_path.parent / f"{input_path.stem}.mp3"
            self.output_entry.delete(0, tk.END)
            self.output_entry.insert(0, str(default_output_file))
            
            self.status_label.config(text="已选择输入文件", fg="blue")

    def select_output_file(self):
        output_file = filedialog.asksaveasfilename(title="保存MP3文件", filetypes=[("MP3 files", "*.mp3")], defaultextension=".mp3")
        if output_file:
            self.output_entry.delete(0, tk.END)
            self.output_entry.insert(0, output_file)

    def cancel_conversion(self):
        """取消转换"""
        if self.conversion_process and self.conversion_process.poll() is None:
            self.conversion_process.terminate()
            self.status_label.config(text="转换已取消", fg="orange")
            self.reset_ui()
    
    def start_conversion_thread(self):
        """开启一个新线程来执行转换操作，以防止GUI卡死"""
        conversion_thread = threading.Thread(target=self.convert_to_mp3, daemon=True)
        conversion_thread.start()

    def reset_ui(self):
        """重置UI状态"""
        self.convert_button.config(state="normal", text="转换")
        self.cancel_button.config(state="disabled")
        self.progress_var.set(0)
    
    def convert_to_mp3(self):
        input_file = self.input_entry.get().strip()
        output_file = self.output_entry.get().strip()
        quality = self.quality_var.get()

        if not input_file or not output_file:
            messagebox.showerror("错误", "请确保已选择输入文件和输出文件位置")
            return
        
        if not Path(input_file).exists():
            messagebox.showerror("错误", "输入文件不存在")
            return
        
        # 更新UI状态
        self.convert_button.config(state="disabled", text="转换中...")
        self.cancel_button.config(state="normal")
        self.status_label.config(text="正在转换...", fg="blue")
        
        try:
            # 使用 ffprobe 获取视频时长
            command = [
                'ffprobe',
                '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                input_file
            ]
            result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW)
            duration = float(result.stdout)

            # 创建 FFmpeg 命令
            command = [
                'ffmpeg', '-y',  # 覆盖输出文件
                '-i', input_file,
                '-vn',  # 不要视频流
                '-acodec', 'libmp3lame',
                '-b:a', quality,  # 设置比特率
                '-metadata', f'converted_by=MP4ToMP3Converter',
                output_file
            ]

            # 异步运行 FFmpeg 并捕获输出
            self.conversion_process = subprocess.Popen(
                command, 
                stderr=subprocess.PIPE, 
                stdout=subprocess.PIPE, 
                universal_newlines=True, 
                creationflags=subprocess.CREATE_NO_WINDOW
            )

            # 解析 FFmpeg 输出，更新进度条
            try:
                for line in self.conversion_process.stderr:
                    if "time=" in line and duration > 0:
                        # 从 FFmpeg 输出中提取转换进度
                        time_str = line.split("time=")[1].split(" ")[0]
                        try:
                            current_time = self.time_str_to_seconds(time_str)
                            progress = min((current_time / duration) * 100, 100)
                            self.update_progress(progress)
                        except (ValueError, IndexError):
                            continue
            except Exception:
                pass  # 如果进程被终止，忽略异常

            # 等待进程结束
            returncode = self.conversion_process.wait()

            if returncode == 0:
                self.update_progress(100)
                self.status_label.config(text="转换完成！", fg="green")
                messagebox.showinfo("成功", f"音频已成功提取到:\n{output_file}")
            elif returncode != -15:  # -15 是SIGTERM，表示用户取消
                self.status_label.config(text="转换失败", fg="red")
                messagebox.showerror("错误", "转换失败，请检查文件格式或FFmpeg设置。")
        
        except FileNotFoundError:
            self.status_label.config(text="FFmpeg未找到", fg="red")
            messagebox.showerror("错误", "未找到FFmpeg程序，请确保已正确安装。")
        except Exception as e:
            self.status_label.config(text="发生错误", fg="red")
            messagebox.showerror("错误", f"转换过程中发生错误:\n{str(e)}")
        finally:
            self.reset_ui()

    def update_progress(self, progress: float):
        """更新进度条"""
        self.progress_var.set(progress)
        if progress < 100:
            self.status_label.config(text=f"转换进度: {progress:.1f}%", fg="blue")
        self.root.update_idletasks()

    def time_str_to_seconds(self, time_str: str) -> float:
        """将 FFmpeg 输出中的时间字符串（如 '00:01:23.45'）转换为秒"""
        try:
            parts = time_str.split(':')
            if len(parts) == 3:
                h, m, s = parts
                return int(h) * 3600 + int(m) * 60 + float(s)
            return 0.0
        except (ValueError, IndexError):
            return 0.0

if __name__ == "__main__":
    root = tk.Tk()
    app = MP4ToMP3Converter(root)
    root.mainloop()
