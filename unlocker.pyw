import tkinter as tk
from tkinter import filedialog, messagebox
from tkinterdnd2 import DND_FILES, TkinterDnD  # 引入拖拽库
import pikepdf
import os

def process_file(file_path):
    """
    核心处理逻辑：接收一个文件路径，执行解锁
    """
    # 【关键】Windows拖拽带空格的路径时，可能会被包裹在 {} 中，需要去除
    if file_path.startswith('{') and file_path.endswith('}'):
        file_path = file_path[1:-1]

    # 简单的格式校验
    if not file_path.lower().endswith('.pdf'):
        messagebox.showwarning("格式错误", "请拖入 PDF 文件！")
        return

    if not os.path.exists(file_path):
        messagebox.showerror("错误", "文件路径不存在或无法读取。")
        return

    try:
        # 打开 PDF
        pdf = pikepdf.open(file_path)
        
        # 准备保存路径
        dir_name = os.path.dirname(file_path)
        base_name = os.path.basename(file_path)
        name_without_ext = os.path.splitext(base_name)[0]
        new_filename = f"{name_without_ext}_unlocked.pdf"
        save_path = os.path.join(dir_name, new_filename)

        # 保存并移除权限
        pdf.save(save_path)
        
        messagebox.showinfo("成功", f"解锁成功！\n文件已保存为：\n{new_filename}")

    except pikepdf.PasswordError:
        messagebox.showerror("失败", "这个文件有“打开密码”，无法直接破解。\n你需要先知道密码才能移除权限。")
    except Exception as e:
        messagebox.showerror("错误", f"发生未知错误：\n{str(e)}")

def select_file():
    """按钮点击事件"""
    file_path = filedialog.askopenfilename(
        title="选择被限制的 PDF 文件",
        filetypes=[("PDF Files", "*.pdf")]
    )
    if file_path:
        process_file(file_path)

def on_drop(event):
    """拖拽释放事件"""
    # event.data 就是拖进来的文件路径
    file_path = event.data
    process_file(file_path)

# --- 主程序 ---

# 注意：这里使用 TkinterDnD.Tk() 而不是标准的 tk.Tk()
root = TkinterDnD.Tk()
root.title("PDF 权限移除工具 (支持拖拽)")
root.geometry("400x200")

# 注册窗口以接受文件拖拽
root.drop_target_register(DND_FILES)
# 绑定“释放”事件到 on_drop 函数
root.dnd_bind('<<Drop>>', on_drop)

# UI 布局
frame = tk.Frame(root)
frame.pack(expand=True, fill='both', padx=20, pady=20)

label_icon = tk.Label(frame, text="📂", font=("Arial", 40))
label_icon.pack()

label_text = tk.Label(frame, text="将 PDF 文件拖拽到这里\n或者", font=("微软雅黑", 12))
label_text.pack(pady=10)

btn = tk.Button(frame, text="点击选择文件", command=select_file, padx=20, pady=5, bg="#4CAF50", fg="black") # Windows FG可能不生效
btn.pack()

root.mainloop()