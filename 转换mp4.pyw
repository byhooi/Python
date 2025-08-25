import subprocess
import tkinter as tk
from tkinter import filedialog, ttk, messagebox
from pathlib import Path
import os
import threading
import re
from typing import Optional, Tuple

def check_ffmpeg_available() -> bool:
    """检查FFmpeg是否可用"""
    try:
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
        return result.returncode == 0
    except FileNotFoundError:
        return False

def get_video_info(file_path: str) -> Optional[Tuple[float, str]]:
    """获取视频信息（时长和分辨率）"""
    try:
        result = subprocess.run(['ffprobe', '-v', 'quiet', '-show_entries', 'format=duration', '-show_entries', 'stream=width,height', '-of', 'csv=p=0', file_path], 
                              capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            duration = float(lines[0]) if lines else 0
            resolution = f"{lines[1]}x{lines[2]}" if len(lines) >= 3 else "未知"
            return duration, resolution
    except:
        pass
    return None

def select_file():
    """选择要转换的视频文件并更新路径"""
    source_path = filedialog.askopenfilename(title="选择要转换的视频文件", 
                                              filetypes=[("视频文件", "*.avi *.mov *.mkv *.wmv *.flv *.mpeg *.mp4")])
    if source_path:
        source_file_path.set(source_path)
        # 设置默认的输出路径
        source_file_name = Path(source_path).stem
        target_file_path.set(str(Path(source_path).parent / f"{source_file_name}_converted.mp4"))
        
        # 获取视频信息
        video_info = get_video_info(source_path)
        if video_info:
            duration, resolution = video_info
            source_info_label.config(text=f"时长: {duration:.1f}s, 分辨率: {resolution}")
        else:
            source_info_label.config(text="无法获取视频信息")

def select_output_file():
    """选择输出文件路径"""
    output_path = filedialog.asksaveasfilename(defaultextension=".mp4", 
                                                  title="选择输出视频文件", 
                                                  filetypes=[("MP4文件", "*.mp4")])
    if output_path:
        target_file_path.set(output_path)

def run_ffmpeg_command(command):
    """运行FFmpeg命令并监控进度"""
    try:
        # 启动FFmpeg进程
        process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, 
                                 stderr=subprocess.STDOUT, universal_newlines=False, 
                                 creationflags=subprocess.CREATE_NO_WINDOW)
        
        # 存储所有输出用于错误诊断
        all_output = []
        
        # 监控输出以获取进度
        total_duration = None
        while True:
            output = process.stdout.readline()
            if output == b'' and process.poll() is not None:
                break
            if output:
                try:
                    # 尝试用UTF-8解码，失败则用GBK
                    try:
                        output_str = output.decode('utf-8')
                    except UnicodeDecodeError:
                        output_str = output.decode('gbk', errors='ignore')
                    
                    all_output.append(output_str)
                    
                    # 解析输出获取进度信息
                    if 'Duration:' in output_str:
                        match = re.search(r'Duration: (\d{2}):(\d{2}):(\d{2}\.\d{2})', output_str)
                        if match:
                            h, m, s = match.groups()
                            total_duration = int(h) * 3600 + int(m) * 60 + float(s)
                    
                    # 获取当前时间
                    if 'time=' in output_str and total_duration:
                        match = re.search(r'time=(\d{2}):(\d{2}):(\d{2}\.\d{2})', output_str)
                        if match:
                            h, m, s = match.groups()
                            current_time = int(h) * 3600 + int(m) * 60 + float(s)
                            progress = (current_time / total_duration) * 100
                            progress_var.set(progress)
                            progress_label.config(text=f"转换进度: {progress:.1f}%")
                            root.update_idletasks()
                except:
                    # 如果解码失败，跳过这一行
                    pass
        
        # 等待进程完成
        return_code = process.wait()
        
        if return_code == 0:
            progress_label.config(text="转换完成！")
            messagebox.showinfo("成功", f"转换完成，已保存为 {target_file_path.get()}")
        else:
            progress_label.config(text="转换失败")
            # 保存错误输出到文件
            error_log_path = Path(target_file_path.get()).parent / "ffmpeg_error.log"
            with open(error_log_path, 'w', encoding='utf-8') as f:
                f.write(f"FFmpeg命令: {command}\n")
                f.write(f"返回码: {return_code}\n")
                f.write(f"错误输出:\n")
                f.write(''.join(all_output))
            
            # 解析Windows错误码
            if return_code == 3199971767:
                error_msg = "Windows系统错误 (0xBEDEAD37): 可能是文件权限问题或文件损坏"
            else:
                error_msg = f"错误代码: {return_code}"
            
            messagebox.showerror("错误", f"转换失败，{error_msg}\n详细错误信息已保存到: {error_log_path}")
            
    except FileNotFoundError:
        progress_label.config(text="FFmpeg未找到")
        messagebox.showerror("错误", "未找到FFmpeg，请确保已正确安装。")
    except Exception as e:
        progress_label.config(text="转换失败")
        messagebox.showerror("错误", f"转换过程中发生错误: {str(e)}")
    finally:
        convert_button.config(state="normal")
        cancel_button.config(state="disabled")
        progress_var.set(0)

def check_file_integrity(file_path: str) -> bool:
    """检查文件完整性和权限"""
    try:
        path = Path(file_path)
        if not path.exists():
            return False
        
        # 检查文件大小
        if path.stat().st_size == 0:
            return False
            
        # 检查文件权限
        if not os.access(file_path, os.R_OK):
            return False
            
        return True
    except:
        return False

def convert_video():
    """执行视频转换"""
    if not source_file_path.get():
        messagebox.showerror("错误", "请先选择一个源视频文件")
        return

    if not target_file_path.get():
        messagebox.showerror("错误", "请选择输出文件路径")
        return

    if not check_ffmpeg_available():
        messagebox.showerror("错误", "未找到FFmpeg，请确保已正确安装。")
        return

    # 检查源文件是否存在
    if not Path(source_file_path.get()).exists():
        messagebox.showerror("错误", "源文件不存在")
        return
        
    # 检查源文件完整性
    if not check_file_integrity(source_file_path.get()):
        messagebox.showerror("错误", "源文件可能损坏或无法访问")
        return

    # 获取转换参数
    quality = quality_var.get()
    crf_values = {"高质量": 23, "中等质量": 30, "低质量": 35}
    crf = crf_values.get(quality, 30)
    
    # 转换中文编码速度为FFmpeg参数
    preset_mapping = {"快速": "fast", "中等": "medium", "慢速": "slow"}
    preset = preset_mapping.get(preset_var.get(), "medium")
    
    # 构建FFmpeg命令
    target_path = target_file_path.get()
    source_path = source_file_path.get()
    
    # 针对MOV文件的优化处理
    if source_path.lower().endswith('.mov'):
        # MOV文件可能需要特殊处理
        ffmpeg_command = f'ffmpeg -i "{source_path}" -c:v libx264 -tag:v avc1 -movflags +faststart -pix_fmt yuv420p -crf {crf} -preset {preset} -c:a aac -b:a 128k "{target_path}"'
    else:
        ffmpeg_command = f'ffmpeg -i "{source_path}" -c:v libx264 -tag:v avc1 -movflags faststart -crf {crf} -preset {preset} "{target_path}"'

    # 禁用转换按钮
    convert_button.config(state="disabled", text="转换中...")
    cancel_button.config(state="normal")
    progress_label.config(text="开始转换...")
    progress_var.set(0)
    
    # 启动新线程以执行转换，避免冻结GUI
    threading.Thread(target=run_ffmpeg_command, args=(ffmpeg_command,), daemon=True).start()

def cancel_conversion():
    """取消转换"""
    messagebox.showinfo("提示", "转换正在进行中，请等待完成")

# 创建主窗口
root = tk.Tk()
root.title("视频转换器 v2.0")
root.geometry("700x500")
root.resizable(True, True)

# 创建主框架
main_frame = tk.Frame(root, padx=20, pady=20)
main_frame.pack(fill=tk.BOTH, expand=True)

# 文件选择区域
file_frame = tk.LabelFrame(main_frame, text="文件选择", padx=10, pady=10)
file_frame.pack(fill=tk.X, pady=(0, 15))

# 源文件路径
source_file_path = tk.StringVar()
tk.Label(file_frame, text="源视频文件:").grid(row=0, column=0, sticky="w", pady=5)
tk.Entry(file_frame, textvariable=source_file_path, width=60).grid(row=0, column=1, padx=5, pady=5)
tk.Button(file_frame, text="选择文件", command=select_file).grid(row=0, column=2, padx=5, pady=5)

# 源文件信息
source_info_label = tk.Label(file_frame, text="请选择视频文件", fg="gray")
source_info_label.grid(row=1, column=0, columnspan=3, sticky="w", pady=2)

# 输出文件路径
target_file_path = tk.StringVar()
tk.Label(file_frame, text="输出视频文件:").grid(row=2, column=0, sticky="w", pady=5)
tk.Entry(file_frame, textvariable=target_file_path, width=60).grid(row=2, column=1, padx=5, pady=5)
tk.Button(file_frame, text="保存位置", command=select_output_file).grid(row=2, column=2, padx=5, pady=5)

# 转换设置区域
settings_frame = tk.LabelFrame(main_frame, text="转换设置", padx=10, pady=10)
settings_frame.pack(fill=tk.X, pady=(0, 15))

# 质量选择
tk.Label(settings_frame, text="视频质量:").grid(row=0, column=0, sticky="w", pady=5)
quality_var = tk.StringVar(value="中等质量")
quality_combo = ttk.Combobox(settings_frame, textvariable=quality_var, 
                           values=["高质量", "中等质量", "低质量"], 
                           state="readonly", width=15)
quality_combo.grid(row=0, column=1, padx=5, pady=5, sticky="w")
tk.Label(settings_frame, text="(高质量文件更大，低质量文件更小)", fg="gray").grid(row=0, column=2, padx=5, pady=5, sticky="w")

# 编码预设
tk.Label(settings_frame, text="编码速度:").grid(row=1, column=0, sticky="w", pady=5)
preset_var = tk.StringVar(value="中等")
preset_combo = ttk.Combobox(settings_frame, textvariable=preset_var, 
                           values=["快速", "中等", "慢速"], 
                           state="readonly", width=15)
preset_combo.grid(row=1, column=1, padx=5, pady=5, sticky="w")
tk.Label(settings_frame, text="(速度越快，压缩率越低)", fg="gray").grid(row=1, column=2, padx=5, pady=5, sticky="w")

# 转换按钮区域
button_frame = tk.Frame(main_frame)
button_frame.pack(fill=tk.X, pady=(0, 15))

convert_button = tk.Button(button_frame, text="开始转换", command=convert_video, 
                          bg="#4CAF50", fg="white", font=("Arial", 12, "bold"), 
                          width=15, height=2)
convert_button.pack(side=tk.LEFT, padx=5)

cancel_button = tk.Button(button_frame, text="取消转换", command=cancel_conversion,
                         bg="#f44336", fg="white", state="disabled", width=15, height=2)
cancel_button.pack(side=tk.LEFT, padx=5)

# 进度显示区域
progress_frame = tk.LabelFrame(main_frame, text="转换进度", padx=10, pady=10)
progress_frame.pack(fill=tk.X, pady=(0, 15))

progress_var = tk.DoubleVar()
progress_bar = ttk.Progressbar(progress_frame, variable=progress_var, maximum=100, length=400)
progress_bar.pack(fill=tk.X, pady=5)

progress_label = tk.Label(progress_frame, text="准备就绪", fg="blue")
progress_label.pack(pady=5)

# FFmpeg状态检查
if not check_ffmpeg_available():
    messagebox.showwarning("警告", "未检测到FFmpeg，请确保已正确安装FFmpeg并添加到系统环境变量中。")

# 启动主循环
root.mainloop()
