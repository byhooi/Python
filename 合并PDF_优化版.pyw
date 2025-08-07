import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path
from typing import List, Optional
from PIL import Image, ImageTk
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
import threading

class DraggableListbox(tk.Listbox):
    def __init__(self, master, **kw):
        super().__init__(master, **kw)
        self.bind('<Button-1>', self.set_current)
        self.bind('<B1-Motion>', self.shift_selection)
        self.curIndex = None
        self.bind('<Double-Button-1>', self.preview_image)

    def set_current(self, event):
        self.curIndex = self.nearest(event.y)

    def shift_selection(self, event):
        i = self.nearest(event.y)
        if i < self.curIndex:
            x = self.get(i)
            self.delete(i)
            self.insert(i + 1, x)
            self.curIndex = i
        elif i > self.curIndex:
            x = self.get(i)
            self.delete(i)
            self.insert(i - 1, x)
            self.curIndex = i
    
    def preview_image(self, event):
        """双击预览图片"""
        selection = self.curselection()
        if selection:
            file_name = self.get(selection[0])
            folder = input_entry.get()
            if folder:
                preview_image(os.path.join(folder, file_name))

def preview_image(image_path: str) -> None:
    """预览图片"""
    try:
        preview_window = tk.Toplevel(root)
        preview_window.title(f"预览 - {Path(image_path).name}")
        preview_window.geometry("600x600")
        
        with Image.open(image_path) as img:
            # 缩放图片以适合预览窗口
            img.thumbnail((550, 550), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            
        label = tk.Label(preview_window, image=photo)
        label.image = photo  # 保持引用
        label.pack(expand=True)
        
    except Exception as e:
        messagebox.showerror("预览错误", f"无法预览图片: {e}")

def convert_images_to_pdf(image_files: List[str], output_file: str, dpi: int = 300, 
                         progress_var: Optional[tk.DoubleVar] = None, 
                         progress_label: Optional[tk.Label] = None) -> None:
    """转换图片为PDF，优化内存使用"""
    if not image_files:
        raise ValueError("没有选择图片文件")

    c = canvas.Canvas(output_file)
    total_files = len(image_files)
    
    for i, img_path in enumerate(image_files, 1):
        try:
            # 使用with语句确保图片正确关闭，释放内存
            with Image.open(img_path) as img:
                # 处理WebP等特殊格式
                if img.format == 'WEBP' or img.mode in ('RGBA', 'LA'):
                    img = img.convert('RGB')
                
                width, height = img.size
                
                # 限制最大尺寸，避免内存溢出
                max_size = 4000  # 像素
                if width > max_size or height > max_size:
                    ratio = min(max_size/width, max_size/height)
                    new_width = int(width * ratio)
                    new_height = int(height * ratio)
                    img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                    width, height = new_width, new_height
                
                # 计算PDF页面大小
                pdf_w = width * 72.0 / dpi
                pdf_h = height * 72.0 / dpi
                c.setPageSize((pdf_w, pdf_h))
                
                # 添加图片到PDF
                c.drawImage(ImageReader(img), 0, 0, width=pdf_w, height=pdf_h)
                c.showPage()

        except Exception as e:
            print(f"处理图片 {img_path} 时出错: {e}")
            continue

        # 更新进度
        if progress_var:
            progress_var.set(int(i / total_files * 100))
        if progress_label:
            progress_label.config(text=f"处理中: {i}/{total_files}")
        root.update_idletasks()

    c.save()

def select_input_folder():
    folder = filedialog.askdirectory(title="选择包含图片的文件夹")
    if folder:
        input_entry.delete(0, tk.END)
        input_entry.insert(0, folder)
        update_file_list(folder)

        # 设置默认输出文件路径
        folder_name = Path(folder).name
        default_output_file = Path(folder) / f"{folder_name}_merged.pdf"
        output_entry.delete(0, tk.END)
        output_entry.insert(0, str(default_output_file))

def update_file_list(folder: str) -> None:
    """更新文件列表"""
    try:
        supported_formats = ('.png', '.jpg', '.jpeg', '.webp', '.bmp', '.tiff', '.gif')
        folder_path = Path(folder)
        
        if not folder_path.exists():
            messagebox.showerror("错误", "文件夹不存在")
            return
            
        image_files = [f.name for f in folder_path.iterdir() 
                      if f.is_file() and f.suffix.lower() in supported_formats]
        
        # 自然排序
        image_files.sort(key=lambda x: [int(c) if c.isdigit() else c for c in x.split()])
        
        file_listbox.delete(0, tk.END)
        for file in image_files:
            file_listbox.insert(tk.END, file)
        
        # 更新状态标签
        status_label.config(text=f"找到 {len(image_files)} 个图片文件", fg="blue")
        
    except Exception as e:
        messagebox.showerror("错误", f"读取文件夹失败: {e}")

def select_output_file():
    file = filedialog.asksaveasfilename(defaultextension=".pdf", 
                                        title="保存PDF文件", 
                                        filetypes=[("PDF files", "*.pdf")])
    if file:
        output_entry.delete(0, tk.END)
        output_entry.insert(0, file)

def remove_selected_files():
    """移除选中的文件"""
    selected_indices = file_listbox.curselection()
    for i in reversed(selected_indices):
        file_listbox.delete(i)
    update_status()

def move_file_up():
    """向上移动选中的文件"""
    selected = file_listbox.curselection()
    if selected and selected[0] > 0:
        idx = selected[0]
        item = file_listbox.get(idx)
        file_listbox.delete(idx)
        file_listbox.insert(idx - 1, item)
        file_listbox.selection_set(idx - 1)

def move_file_down():
    """向下移动选中的文件"""
    selected = file_listbox.curselection()
    if selected and selected[0] < file_listbox.size() - 1:
        idx = selected[0]
        item = file_listbox.get(idx)
        file_listbox.delete(idx)
        file_listbox.insert(idx + 1, item)
        file_listbox.selection_set(idx + 1)

def update_status():
    """更新状态信息"""
    count = file_listbox.size()
    status_label.config(text=f"待转换: {count} 个文件", fg="green" if count > 0 else "gray")

def convert_in_thread():
    """在新线程中执行转换"""
    input_folder = input_entry.get().strip()
    output_file = output_entry.get().strip()
    
    try:
        dpi = int(dpi_entry.get())
        if dpi < 72 or dpi > 600:
            raise ValueError("DPI应在72-600之间")
    except ValueError as e:
        messagebox.showerror("参数错误", f"DPI设置无效: {e}")
        return

    if not input_folder or not output_file:
        messagebox.showerror("错误", "请选择输入文件夹和输出文件")
        return

    if not Path(input_folder).exists():
        messagebox.showerror("错误", "输入文件夹不存在")
        return
        
    if file_listbox.size() == 0:
        messagebox.showerror("错误", "没有图片文件可转换")
        return

    try:
        progress_var.set(0)
        progress_label.config(text="准备中...")
        convert_button.config(state=tk.DISABLED, text="转换中...")
        cancel_button.config(state=tk.NORMAL)
        root.update_idletasks()

        # 构建完整的文件路径列表
        image_files = [os.path.join(input_folder, file_listbox.get(i)) 
                      for i in range(file_listbox.size())]
        
        # 验证所有文件是否存在
        missing_files = [f for f in image_files if not Path(f).exists()]
        if missing_files:
            messagebox.showerror("错误", f"以下文件不存在:\n" + "\n".join(missing_files[:5]))
            return
        
        convert_images_to_pdf(image_files, output_file, dpi, progress_var, progress_label)

        progress_label.config(text="转换完成！")
        messagebox.showinfo("成功", f"PDF文件已成功生成:\n{output_file}")
        
    except Exception as e:
        progress_label.config(text="转换失败")
        messagebox.showerror("错误", f"转换过程中发生错误:\n{str(e)}")
    finally:
        convert_button.config(state=tk.NORMAL, text="开始转换")
        cancel_button.config(state=tk.DISABLED)

def convert():
    """开始转换（在新线程中）"""
    global conversion_thread
    conversion_thread = threading.Thread(target=convert_in_thread, daemon=True)
    conversion_thread.start()

def cancel_conversion():
    """取消转换"""
    # 这里可以添加取消逻辑，但由于reportlab转换是同步的，实际上很难中途取消
    messagebox.showinfo("提示", "转换正在进行中，请等待完成")

# 创建主窗口
root = tk.Tk()
root.title("图片到PDF转换器 v2.0")
root.geometry("800x650")
root.resizable(True, True)

# 创建主框架
main_frame = tk.Frame(root, padx=10, pady=10)
main_frame.pack(fill=tk.BOTH, expand=True)

# 输入文件夹选择
input_frame = tk.Frame(main_frame)
input_frame.pack(fill=tk.X, pady=(0, 10))
tk.Label(input_frame, text="图片文件夹:", width=12, anchor="w").pack(side=tk.LEFT)
input_entry = tk.Entry(input_frame)
input_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 5))
tk.Button(input_frame, text="浏览", command=select_input_folder, width=8).pack(side=tk.RIGHT)

# 文件列表和控制按钮
list_frame = tk.Frame(main_frame)
list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

# 左侧：文件列表
list_left = tk.Frame(list_frame)
list_left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

tk.Label(list_left, text="图片文件列表（双击预览，拖拽排序）:").pack(anchor="w")
file_listbox = DraggableListbox(list_left, selectmode=tk.SINGLE, height=12)
file_listbox.pack(fill=tk.BOTH, expand=True, pady=(5, 0))

# 右侧：控制按钮
button_frame = tk.Frame(list_frame, width=100)
button_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))
button_frame.pack_propagate(False)

tk.Button(button_frame, text="↑ 上移", command=move_file_up, width=12).pack(pady=2)
tk.Button(button_frame, text="↓ 下移", command=move_file_down, width=12).pack(pady=2)
tk.Button(button_frame, text="移除选中", command=remove_selected_files, width=12).pack(pady=2)

# 输出文件和设置
output_frame = tk.Frame(main_frame)
output_frame.pack(fill=tk.X, pady=(0, 10))

# 输出文件选择
output_row1 = tk.Frame(output_frame)
output_row1.pack(fill=tk.X)
tk.Label(output_row1, text="输出PDF文件:", width=12, anchor="w").pack(side=tk.LEFT)
output_entry = tk.Entry(output_row1)
output_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 5))
tk.Button(output_row1, text="浏览", command=select_output_file, width=8).pack(side=tk.RIGHT)

# DPI设置
output_row2 = tk.Frame(output_frame)
output_row2.pack(fill=tk.X, pady=(5, 0))
tk.Label(output_row2, text="图片质量(DPI):", width=12, anchor="w").pack(side=tk.LEFT)
dpi_entry = tk.Entry(output_row2, width=10)
dpi_entry.insert(0, "300")
dpi_entry.pack(side=tk.LEFT, padx=(5, 10))
tk.Label(output_row2, text="(72-600, 推荐300)", fg="gray").pack(side=tk.LEFT)

# 控制按钮
control_frame = tk.Frame(main_frame)
control_frame.pack(fill=tk.X, pady=(0, 10))

convert_button = tk.Button(control_frame, text="开始转换", command=convert, 
                          bg="#4CAF50", fg="white", font=("Arial", 10, "bold"), height=2)
convert_button.pack(side=tk.LEFT, padx=(0, 10))

cancel_button = tk.Button(control_frame, text="取消转换", command=cancel_conversion,
                         bg="#f44336", fg="white", state="disabled")
cancel_button.pack(side=tk.LEFT)

# 进度条和状态
progress_frame = tk.Frame(main_frame)
progress_frame.pack(fill=tk.X)

progress_var = tk.IntVar()
progress_bar = ttk.Progressbar(progress_frame, variable=progress_var, maximum=100)
progress_bar.pack(fill=tk.X, pady=(0, 5))

progress_label = tk.Label(progress_frame, text="准备中...")
status_label = tk.Label(progress_frame, text="请选择图片文件夹开始", fg="gray")
progress_label.pack()
status_label.pack()

# 全局变量
conversion_thread = None

# 绑定文件列表选择事件
file_listbox.bind('<<ListboxSelect>>', lambda e: update_status())

root.mainloop()