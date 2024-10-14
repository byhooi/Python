import subprocess
from tkinter import filedialog, Tk, Label, Button, StringVar, Frame, messagebox
import os
import threading

def select_file():
    """选择要转换的视频文件并更新路径"""
    source_path = filedialog.askopenfilename(title="选择要转换的视频文件", 
                                              filetypes=[("视频文件", "*.avi *.mov *.mkv *.wmv *.flv *.mpeg *.mp4")])
    if source_path:
        source_file_path.set(source_path)
        # 设置默认的输出路径
        source_file_name = os.path.splitext(os.path.basename(source_path))[0]
        target_file_path.set(os.path.join(os.path.dirname(source_path), source_file_name + "_converted.mp4"))

def select_output_file():
    """选择输出文件路径"""
    output_path = filedialog.asksaveasfilename(defaultextension=".mp4", 
                                                  title="选择输出视频文件", 
                                                  filetypes=[("MP4文件", "*.mp4")])
    if output_path:
        target_file_path.set(output_path)

def run_ffmpeg_command(command):
    """运行FFmpeg命令"""
    try:
        # 运行FFmpeg命令，隐藏窗口
        subprocess.run(command, shell=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
        messagebox.showinfo("成功", f"转换完成，已保存为 {target_file_path.get()}")
    except subprocess.CalledProcessError as e:
        messagebox.showerror("错误", f"转换失败，错误代码: {e.returncode}")
    except FileNotFoundError:
        messagebox.showerror("错误", "未找到FFmpeg，请确保已正确安装。")
    finally:
        convert_button.config(state="normal")  # 转换完成后恢复按钮状态

def convert_video():
    """执行视频转换"""
    if not source_file_path.get():
        messagebox.showerror("错误", "请先选择一个源视频文件")
        return

    target_path = target_file_path.get()
    ffmpeg_command = f'ffmpeg -i "{source_file_path.get()}" -c:v libx264 -tag:v avc1 -movflags faststart -crf 30 -preset superfast "{target_path}"'

    # 禁用转换按钮
    convert_button.config(state="disabled")
    
    # 启动新线程以执行转换，避免冻结GUI
    threading.Thread(target=run_ffmpeg_command, args=(ffmpeg_command,)).start()

# 创建主窗口
root = Tk()
root.title("视频转换器")

# 创建框架
frame = Frame(root, padx=10, pady=10)
frame.pack(padx=10, pady=10)

# 源文件路径
source_file_path = StringVar()
Label(frame, text="源视频文件:").grid(row=0, column=0, sticky="e")
Label(frame, textvariable=source_file_path, width=50, anchor='w').grid(row=0, column=1, padx=5, pady=5)
Button(frame, text="选择文件", command=select_file).grid(row=0, column=2)

# 输出文件路径
target_file_path = StringVar()
Label(frame, text="输出视频文件:").grid(row=1, column=0, sticky="e")
Label(frame, textvariable=target_file_path, width=50, anchor='w').grid(row=1, column=1, padx=5, pady=5)
Button(frame, text="保存位置", command=select_output_file).grid(row=1, column=2)

# 转换按钮
convert_button = Button(frame, text="开始转换", command=convert_video)
convert_button.grid(row=2, column=1, pady=10)

# 启动主循环
root.mainloop()
