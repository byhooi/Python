"""PDF 权限移除工具，支持文件选择和拖放。"""

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Iterable

import pikepdf

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
except ImportError:
    DND_FILES = None
    TkinterDnD = None


def unlock_pdf(file_path: Path) -> Path:
    """移除 PDF 权限限制，并返回输出路径。"""
    source = file_path.expanduser().resolve()
    if source.suffix.lower() != ".pdf":
        raise ValueError("请选择 PDF 文件")
    if not source.is_file():
        raise FileNotFoundError(f"文件不存在或无法读取：{source}")

    output = source.with_name(f"{source.stem}_unlocked.pdf")
    with pikepdf.open(source) as pdf:
        pdf.save(output)
    return output


class PdfUnlockerApp:
    def __init__(self, root: tk.Tk, dnd_available: bool) -> None:
        self.root = root
        self.root.title("PDF 权限移除工具")
        self.root.geometry("440x230")
        self.root.resizable(False, False)

        frame = tk.Frame(root)
        frame.pack(expand=True, fill="both", padx=20, pady=20)

        tk.Label(frame, text="PDF", font=("Arial", 30, "bold")).pack()
        hint = "将 PDF 文件拖放到这里\n或者" if dnd_available else "请选择需要移除权限的 PDF 文件"
        self.hint_label = tk.Label(frame, text=hint, font=("Microsoft YaHei", 11))
        self.hint_label.pack(pady=10)
        tk.Button(frame, text="点击选择文件", command=self.select_file, padx=20, pady=5).pack()

        if dnd_available:
            root.drop_target_register(DND_FILES)
            root.dnd_bind("<<Drop>>", self.on_drop)

    def process_files(self, paths: Iterable[str]) -> None:
        errors = []
        outputs = []
        for raw_path in paths:
            path = Path(raw_path)
            try:
                output = path.resolve().with_name(f"{path.stem}_unlocked.pdf")
                if output.exists() and not messagebox.askyesno(
                    "确认覆盖", f"文件已存在，是否覆盖？\n{output.name}"
                ):
                    continue
                outputs.append(unlock_pdf(path))
            except pikepdf.PasswordError:
                errors.append(f"{path.name}：存在打开密码，需要先提供密码")
            except (OSError, ValueError) as error:
                errors.append(f"{path.name}：{error}")

        if outputs:
            names = "\n".join(path.name for path in outputs)
            messagebox.showinfo("完成", f"已处理 {len(outputs)} 个文件：\n{names}")
        if errors:
            messagebox.showerror("部分文件处理失败", "\n".join(errors))

    def select_file(self) -> None:
        paths = filedialog.askopenfilenames(
            title="选择被限制的 PDF 文件", filetypes=[("PDF 文件", "*.pdf")]
        )
        if paths:
            self.process_files(paths)

    def on_drop(self, event) -> None:
        paths = self.root.tk.splitlist(event.data)
        self.process_files(paths)


def main() -> None:
    dnd_available = TkinterDnD is not None
    root = TkinterDnD.Tk() if dnd_available else tk.Tk()
    PdfUnlockerApp(root, dnd_available)
    if not dnd_available:
        messagebox.showwarning("拖放不可用", "未安装 tkinterdnd2，仍可通过按钮选择文件。")
    root.mainloop()


if __name__ == "__main__":
    main()
