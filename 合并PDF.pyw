import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

class DraggableListbox(tk.Listbox):
    def __init__(self, master, **kw):
        super().__init__(master, **kw)
        self.bind('<Button-1>', self.set_current)
        self.bind('<B1-Motion>', self.shift_selection)
        self.curIndex = None

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

def convert_images_to_pdf(image_files, output_file, dpi=300, progress_var=None, progress_label=None):
    if not image_files:
        raise ValueError("没有选择图片文件")

    c = canvas.Canvas(output_file)
    total_files = len(image_files)
    
    for i, img_path in enumerate(image_files, 1):
        with Image.open(img_path) as img:
            if img.format == 'WEBP':
                img = img.convert('RGB')
            width, height = img.size
            pdf_w = width * 72.0 / dpi
            pdf_h = height * 72.0 / dpi
            c.setPageSize((pdf_w, pdf_h))
            c.drawImage(ImageReader(img), 0, 0, width=pdf_w, height=pdf_h)
            c.showPage()

        if progress_var:
            progress_var.set(int(i / total_files * 100))
        if progress_label:
            progress_label.config(text=f"处理中: {i}/{total_files}")
        root.update_idletasks()

    c.save()

def select_input_folder():
    folder = filedialog.askdirectory()
    if folder:
        input_entry.delete(0, tk.END)
        input_entry.insert(0, folder)
        update_file_list(folder)

        # 设置默认输出文件路径
        default_output_file = os.path.join(folder, "output.pdf")
        output_entry.delete(0, tk.END)
        output_entry.insert(0, default_output_file)  # 显示默认输出路径

def update_file_list(folder):
    supported_formats = ('.png', '.jpg', '.jpeg', '.webp')
    image_files = [f for f in os.listdir(folder) if f.lower().endswith(supported_formats)]
    image_files.sort()
    file_listbox.delete(0, tk.END)
    for file in image_files:
        file_listbox.insert(tk.END, file)

def select_output_file():
    file = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF files", "*.pdf")])
    if file:
        output_entry.delete(0, tk.END)
        output_entry.insert(0, file)

def convert():
    input_folder = input_entry.get()
    output_file = output_entry.get()
    dpi = int(dpi_entry.get())

    if not input_folder or not output_file:
        messagebox.showerror("错误", "请选择输入文件夹和输出文件")
        return

    try:
        progress_var.set(0)
        progress_label.config(text="准备中...")
        convert_button.config(state=tk.DISABLED)
        root.update_idletasks()

        image_files = [os.path.join(input_folder, file_listbox.get(i)) for i in range(file_listbox.size())]
        convert_images_to_pdf(image_files, output_file, dpi, progress_var, progress_label)

        progress_label.config(text="完成!")
        messagebox.showinfo("成功", "PDF文件已成功生成")
    except Exception as e:
        messagebox.showerror("错误", str(e))
    finally:
        convert_button.config(state=tk.NORMAL)

# 创建主窗口
root = tk.Tk()
root.title("图片到PDF转换器")

# 输入文件夹选择
tk.Label(root, text="图片文件夹:").grid(row=0, column=0, sticky="e", padx=5, pady=5)
input_entry = tk.Entry(root, width=50)
input_entry.grid(row=0, column=1, padx=5, pady=5)
tk.Button(root, text="浏览", command=select_input_folder).grid(row=0, column=2, padx=5, pady=5)

# 文件列表
file_listbox = DraggableListbox(root, selectmode=tk.SINGLE, width=70, height=10)
file_listbox.grid(row=1, column=0, columnspan=3, padx=5, pady=5)

# 输出文件选择
tk.Label(root, text="输出PDF文件:").grid(row=2, column=0, sticky="e", padx=5, pady=5)
output_entry = tk.Entry(root, width=50)
output_entry.grid(row=2, column=1, padx=5, pady=5)
tk.Button(root, text="浏览", command=select_output_file).grid(row=2, column=2, padx=5, pady=5)

# DPI设置
tk.Label(root, text="DPI:").grid(row=3, column=0, sticky="e", padx=5, pady=5)
dpi_entry = tk.Entry(root, width=10)
dpi_entry.insert(0, "300")
dpi_entry.grid(row=3, column=1, sticky="w", padx=5, pady=5)

# 进度条
progress_var = tk.IntVar()
progress_bar = ttk.Progressbar(root, variable=progress_var, maximum=100)
progress_bar.grid(row=4, column=0, columnspan=3, sticky="ew", padx=5, pady=5)

# 进度标签
progress_label = tk.Label(root, text="")
progress_label.grid(row=5, column=0, columnspan=3)

# 转换按钮
convert_button = tk.Button(root, text="转换", command=convert)
convert_button.grid(row=6, column=1, pady=10)

root.mainloop()
