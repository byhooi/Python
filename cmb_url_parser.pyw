"""从多层 URL 编码中提取 OpenId 和 UnionId。"""

import tkinter as tk
from collections import deque
from tkinter import messagebox, scrolledtext
from typing import Dict, Optional
from urllib.parse import parse_qs, unquote, urlencode, urlparse


JUMP_URL = "http://jump.m.cmbchina.com/ZEEUsFCX"
MAX_DECODE_ROUNDS = 20


def extract_params(url: str) -> Dict[str, str]:
    """提取 URL 第一层查询参数，保留空值。"""
    parsed = urlparse(url)
    params = parse_qs(parsed.query, keep_blank_values=True)
    return {key: values[0] for key, values in params.items() if values}


def parse_openid_unionid(url: str) -> Dict[str, Optional[str]]:
    """递归解码 URL，并以不区分大小写的方式提取目标参数。"""
    results: Dict[str, Optional[str]] = {"OpenId": None, "UnionId": None}
    seen = set()
    pending = deque([url.strip()])

    while pending and len(seen) < MAX_DECODE_ROUNDS:
        current_url = pending.popleft()
        if not current_url or current_url in seen:
            continue
        seen.add(current_url)

        raw_params = extract_params(current_url)
        params = {key.casefold(): value for key, value in raw_params.items()}
        results["OpenId"] = results["OpenId"] or params.get("openid")
        results["UnionId"] = results["UnionId"] or params.get("unionid")
        if all(results.values()):
            break

        # 查询参数的值本身也可能是一条经过编码的 URL。
        for value in raw_params.values():
            pending.append(value)
            pending.append(unquote(value))

        decoded = unquote(current_url)
        if decoded != current_url:
            pending.append(decoded)

    return results


def build_jump_url(openid: str, unionid: str) -> str:
    """安全编码参数并生成跳转 URL。"""
    return f"{JUMP_URL}?{urlencode({'UnionId': unionid, 'OpenId': openid})}"


class UrlParserApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.generated_url = ""
        self.root.title("URL 解析工具（安全本地版）")
        self.root.geometry("650x400")
        self.root.minsize(520, 360)
        self.root.configure(bg="#f8f9fa")
        self._build_ui()

    def _build_ui(self) -> None:
        tk.Label(
            self.root,
            text="请输入要解析的 URL：",
            bg="#f8f9fa",
            font=("Microsoft YaHei", 11),
        ).pack(anchor="w", padx=10, pady=(10, 0))

        self.text_area = scrolledtext.ScrolledText(
            self.root, wrap=tk.WORD, font=("Consolas", 10), height=8, width=75
        )
        self.text_area.pack(fill="both", expand=True, padx=10, pady=10)

        button_frame = tk.Frame(self.root, bg="#f8f9fa")
        button_frame.pack(pady=5)
        tk.Button(button_frame, text="清空", command=self.clear, width=15).grid(
            row=0, column=0, padx=10
        )
        tk.Button(button_frame, text="解析", command=self.parse, width=15).grid(
            row=0, column=1, padx=10
        )
        self.copy_button = tk.Button(
            button_frame, text="复制 URL", command=self.copy, width=15, state="disabled"
        )
        self.copy_button.grid(row=0, column=2, padx=10)

        self.result_label = tk.Label(
            self.root,
            text="解析结果将在这里显示。",
            bg="#f8f9fa",
            font=("Consolas", 10),
            justify="left",
            anchor="w",
            wraplength=600,
        )
        self.result_label.pack(fill="x", padx=10, pady=20)

    def clear(self) -> None:
        if not self.text_area.get("1.0", tk.END).strip():
            return
        if messagebox.askyesno("确认清空", "确定要清空所有内容吗？"):
            self.text_area.delete("1.0", tk.END)
            self.generated_url = ""
            self.result_label.config(text="解析结果将在这里显示。")
            self.copy_button.config(state="disabled")

    def parse(self) -> None:
        url = self.text_area.get("1.0", tk.END).strip()
        if not url:
            messagebox.showwarning("提示", "请输入 URL！")
            return

        results = parse_openid_unionid(url)
        if not results["OpenId"] or not results["UnionId"]:
            self.generated_url = ""
            self.result_label.config(text="解析失败，未同时找到 OpenId 和 UnionId。")
            self.copy_button.config(state="disabled")
            messagebox.showerror("解析失败", "未同时找到 OpenId 和 UnionId 参数。")
            return

        self.generated_url = build_jump_url(results["OpenId"], results["UnionId"])
        self.result_label.config(text=f"生成的 URL：\n{self.generated_url}")
        self.copy_button.config(state="normal")

    def copy(self) -> None:
        if not self.generated_url:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(self.generated_url)
        self.root.update_idletasks()
        messagebox.showinfo("复制成功", "URL 已复制到剪贴板！")


def main() -> None:
    root = tk.Tk()
    UrlParserApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
