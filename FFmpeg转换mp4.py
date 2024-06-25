import subprocess
from tkinter import filedialog
from tkinter import Tk
import os

# 创建一个Tkinter根窗口以打开文件对话框
root = Tk()
root.withdraw()  # 隐藏根窗口

# 打开文件对话框以选择源文件
source_file_path = filedialog.askopenfilename(title="选择要转换的视频文件", filetypes=[("视频文件", "*.avi *.mov *.mkv *.wmv *.flv *.mpeg *.mp4")])

if source_file_path:
    # 获取源文件的基本名称（不包括扩展名）
    source_file_name = os.path.splitext(os.path.basename(source_file_path))[0]

    # 构建目标文件的完整路径，如果源文件也是.mp4，则添加后缀
    target_file_path = os.path.join(os.path.dirname(source_file_path), source_file_name + "_converted.mp4")

    # 定义FFmpeg命令
    ffmpeg_command = f"ffmpeg -i \"{source_file_path}\" -c:v libx264 -c:a aac \"{target_file_path}\""

    try:
        # 执行FFmpeg命令
        subprocess.run(ffmpeg_command, shell=True, check=True)
        print("转换完成，已保存为 " + target_file_path)
    except subprocess.CalledProcessError as e:
        print(f"转换失败，错误代码: {e.returncode}")
    except FileNotFoundError:
        print("未找到FFmpeg，请确保已正确安装。")
else:
    print("未选择源文件。")
