import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import subprocess
import threading

class MP4ToMP3Converter:
    def __init__(self, root):
        self.root = root
        self.root.title("MP4 到 MP3 转换器")
        self.root.geometry("400x300")  # 设置窗口大小
        
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

        # 转换按钮
        self.convert_button = tk.Button(root, text="转换", command=self.start_conversion_thread)
        self.convert_button.grid(row=4, column=0, columnspan=2, pady=20)

        # 进度条
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(root, variable=self.progress_var, maximum=100)
        self.progress_bar.grid(row=5, column=0, columnspan=2, padx=10, pady=10, sticky="ew")

        # 状态标签
        self.status_label = tk.Label(root, text="")
        self.status_label.grid(row=6, column=0, columnspan=2)

    def select_input_file(self):
        input_file = filedialog.askopenfilename(title="选择MP4文件", filetypes=[("MP4 files", "*.mp4")])
        if input_file:
            self.input_entry.delete(0, tk.END)
            self.input_entry.insert(0, input_file)

            # 自动设置 MP3 输出文件的默认路径
            default_output_file = os.path.splitext(input_file)[0] + ".mp3"
            self.output_entry.delete(0, tk.END)
            self.output_entry.insert(0, default_output_file)

    def select_output_file(self):
        output_file = filedialog.asksaveasfilename(title="保存MP3文件", filetypes=[("MP3 files", "*.mp3")], defaultextension=".mp3")
        if output_file:
            self.output_entry.delete(0, tk.END)
            self.output_entry.insert(0, output_file)

    def start_conversion_thread(self):
        """开启一个新线程来执行转换操作，以防止GUI卡死"""
        conversion_thread = threading.Thread(target=self.convert_to_mp3)
        conversion_thread.start()

    def convert_to_mp3(self):
        input_file = self.input_entry.get()
        output_file = self.output_entry.get()

        if not input_file or not output_file:
            messagebox.showerror("错误", "请确保已选择 MP4 输入文件和 MP3 输出文件位置")
            return

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
                'ffmpeg',
                '-i', input_file,
                '-vn',  # 不要视频流
                '-acodec', 'libmp3lame',
                output_file
            ]

            # 异步运行 FFmpeg 并捕获输出
            process = subprocess.Popen(command, stderr=subprocess.PIPE, stdout=subprocess.PIPE, universal_newlines=True, creationflags=subprocess.CREATE_NO_WINDOW)

            # 解析 FFmpeg 输出，更新进度条
            for line in process.stderr:
                if "time=" in line:
                    # 从 FFmpeg 输出中提取转换进度
                    time_str = line.split("time=")[1].split(" ")[0]
                    current_time = self.time_str_to_seconds(time_str)
                    progress = (current_time / duration) * 100
                    self.update_progress(progress)

            # 等待进程结束
            process.wait()

            if process.returncode == 0:
                messagebox.showinfo("成功", f"音频已成功提取到 {output_file}")
                self.update_progress(100)  # 确保进度条完成
            else:
                messagebox.showerror("错误", "转换失败，请检查文件格式。")
        
        except Exception as e:
            messagebox.showerror("错误", f"发生错误: {e}")

    def update_progress(self, progress):
        """更新进度条"""
        self.progress_var.set(progress)
        self.status_label.config(text=f"进度: {progress:.2f}%")
        self.root.update_idletasks()

    def time_str_to_seconds(self, time_str):
        """将 FFmpeg 输出中的时间字符串（如 '00:01:23.45'）转换为秒"""
        h, m, s = time_str.split(':')
        s = float(s)
        return int(h) * 3600 + int(m) * 60 + s

if __name__ == "__main__":
    root = tk.Tk()
    app = MP4ToMP3Converter(root)
    root.mainloop()
