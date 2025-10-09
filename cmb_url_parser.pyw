import tkinter as tk
from tkinter import messagebox, scrolledtext
import urllib.parse


def extract_params(url: str) -> dict:
    parsed = urllib.parse.urlparse(url)
    params = urllib.parse.parse_qs(parsed.query)
    return {k: v[0] for k, v in params.items()}


def parse_openid_unionid(url: str):
    seen = set()
    results = {"OpenId": None, "UnionId": None}
    current_url = url.strip()

    while current_url and current_url not in seen:
        seen.add(current_url)
        params = extract_params(current_url)
        if "OpenId" in params and not results["OpenId"]:
            results["OpenId"] = params["OpenId"]
        if "UnionId" in params and not results["UnionId"]:
            results["UnionId"] = params["UnionId"]

        try:
            decoded = urllib.parse.unquote(current_url)
        except Exception:
            break
        if decoded == current_url:
            break
        current_url = decoded

    return results


def on_clear():
    if text_area.get("1.0", tk.END).strip() == "":
        return
    if messagebox.askyesno("确认清空", "确定要清空所有内容吗？"):
        text_area.delete("1.0", tk.END)
        result_label.config(text="解析结果将在这里显示。")
        copy_btn.config(state="disabled")


def on_parse():
    url = text_area.get("1.0", tk.END).strip()
    if not url:
        messagebox.showwarning("提示", "请输入 URL！")
        return

    results = parse_openid_unionid(url)
    if not results["OpenId"] or not results["UnionId"]:
        messagebox.showerror("解析失败", "未找到 OpenId 或 UnionId 参数。")
        result_label.config(text="解析失败，未找到相关参数。")
        copy_btn.config(state="disabled")
        return

    generated_url = f"http://jump.m.cmbchina.com/ZEEUsFCX?UnionId={results['UnionId']}&OpenId={results['OpenId']}"
    result_label.config(text=f"生成的 URL：\n{generated_url}")
    copy_btn.config(state="normal")


def on_copy():
    url_text = result_label.cget("text").replace("生成的 URL：\n", "").strip()
    if not url_text:
        return
    root.clipboard_clear()
    root.clipboard_append(url_text)
    messagebox.showinfo("复制成功", "URL 已复制到剪贴板！")


# 初始化窗口
root = tk.Tk()
root.title("URL 解析工具（安全本地版）")
root.geometry("650x400")
root.configure(bg="#f8f9fa")

# 输入框
tk.Label(root, text="请输入要解析的 URL：", bg="#f8f9fa", font=("Microsoft YaHei", 11)).pack(anchor="w", padx=10, pady=(10, 0))
text_area = scrolledtext.ScrolledText(root, wrap=tk.WORD, font=("Consolas", 10), height=8, width=75)
text_area.pack(padx=10, pady=10)

# 按钮区域
button_frame = tk.Frame(root, bg="#f8f9fa")
button_frame.pack(pady=5)
tk.Button(button_frame, text="清空", command=on_clear, bg="#6b7280", fg="white", font=("Microsoft YaHei", 10), width=15).grid(row=0, column=0, padx=10)
tk.Button(button_frame, text="解析", command=on_parse, bg="#4096ff", fg="white", font=("Microsoft YaHei", 10), width=15).grid(row=0, column=1, padx=10)
copy_btn = tk.Button(button_frame, text="复制 URL", command=on_copy, bg="#10b981", fg="white", font=("Microsoft YaHei", 10), width=15, state="disabled")
copy_btn.grid(row=0, column=2, padx=10)

# 结果显示
result_label = tk.Label(root, text="解析结果将在这里显示。", bg="#f8f9fa", font=("Consolas", 10), justify="left", anchor="w", wraplength=600)
result_label.pack(fill="both", padx=10, pady=20)

root.mainloop()
