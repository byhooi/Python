"""将文件夹中的图片按指定顺序合并为 PDF。"""

import re
import tempfile
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Callable, List, Optional, Tuple

from PIL import Image, ImageTk

try:
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas
except ModuleNotFoundError:
    ImageReader = None
    canvas = None


SUPPORTED_FORMATS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".gif"}
MAX_IMAGE_SIZE = 4000


class ConversionCancelled(Exception):
    """用户主动取消转换。"""


def natural_sort_key(value: str) -> List[Tuple[int, object]]:
    """生成支持数字片段的自然排序键。"""
    return [
        (0, int(part)) if part.isdigit() else (1, part.casefold())
        for part in re.split(r"(\d+)", value)
    ]


def convert_images_to_pdf(
    image_files: List[Path],
    output_file: Path,
    dpi: int = 300,
    progress_callback: Optional[Callable[[int, int], None]] = None,
    cancel_event: Optional[threading.Event] = None,
) -> Tuple[int, List[str]]:
    """原子生成 PDF，返回成功页数和失败信息。"""
    if not image_files:
        raise ValueError("没有选择图片文件")
    if not 72 <= dpi <= 600:
        raise ValueError("DPI 应在 72-600 之间")
    if canvas is None or ImageReader is None:
        raise RuntimeError("缺少 reportlab，请先运行：pip install reportlab")

    output_file.parent.mkdir(parents=True, exist_ok=True)
    temp_handle = tempfile.NamedTemporaryFile(
        suffix=".pdf", prefix=f".{output_file.stem}_", dir=output_file.parent, delete=False
    )
    temp_path = Path(temp_handle.name)
    temp_handle.close()
    pdf = canvas.Canvas(str(temp_path))
    success_count = 0
    errors: List[str] = []

    try:
        for index, image_path in enumerate(image_files, 1):
            if cancel_event and cancel_event.is_set():
                raise ConversionCancelled

            try:
                with Image.open(image_path) as source:
                    source.seek(0)
                    source.thumbnail((MAX_IMAGE_SIZE, MAX_IMAGE_SIZE), Image.Resampling.LANCZOS)
                    with source.convert("RGB") as image:
                        width, height = image.size
                        if width <= 0 or height <= 0:
                            raise ValueError("图片尺寸无效")
                        pdf_width = width * 72.0 / dpi
                        pdf_height = height * 72.0 / dpi
                        pdf.setPageSize((pdf_width, pdf_height))
                        pdf.drawImage(
                            ImageReader(image),
                            0,
                            0,
                            width=pdf_width,
                            height=pdf_height,
                        )
                        pdf.showPage()
                        success_count += 1
            except (OSError, ValueError) as error:
                errors.append(f"{image_path.name}：{error}")

            if progress_callback:
                progress_callback(index, len(image_files))

        if success_count == 0:
            raise RuntimeError("所有图片都处理失败，未生成 PDF")
        pdf.save()
        temp_path.replace(output_file)
    except BaseException:
        try:
            # canvas 尚未正常保存时也应删除临时文件。
            temp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise

    return success_count, errors


class DraggableListbox(tk.Listbox):
    def __init__(self, master, on_reorder: Callable[[], None], **kwargs) -> None:
        super().__init__(master, **kwargs)
        self.current_index: Optional[int] = None
        self.on_reorder = on_reorder
        self.bind("<Button-1>", self._set_current)
        self.bind("<B1-Motion>", self._shift_selection)

    def _set_current(self, event) -> None:
        self.current_index = self.nearest(event.y)

    def _shift_selection(self, event) -> None:
        if self.current_index is None or self.size() < 2:
            return
        new_index = self.nearest(event.y)
        if new_index == self.current_index:
            return
        item = self.get(self.current_index)
        self.delete(self.current_index)
        self.insert(new_index, item)
        self.selection_clear(0, tk.END)
        self.selection_set(new_index)
        self.current_index = new_index
        self.on_reorder()


class ImageToPdfApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("图片到 PDF 转换器 v3.0")
        self.root.geometry("820x660")
        self.root.minsize(700, 560)
        self.input_folder: Optional[Path] = None
        self.files: List[Path] = []
        self.cancel_event = threading.Event()
        self.progress_var = tk.IntVar()
        self._build_ui()

    def _build_ui(self) -> None:
        main_frame = tk.Frame(self.root, padx=10, pady=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        input_frame = tk.Frame(main_frame)
        input_frame.pack(fill=tk.X, pady=(0, 10))
        tk.Label(input_frame, text="图片文件夹:", width=12, anchor="w").pack(side=tk.LEFT)
        self.input_entry = tk.Entry(input_frame)
        self.input_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.input_button = tk.Button(input_frame, text="浏览", command=self.select_input_folder)
        self.input_button.pack(side=tk.RIGHT)

        list_frame = tk.Frame(main_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        list_left = tk.Frame(list_frame)
        list_left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tk.Label(list_left, text="图片列表（双击预览，拖动排序）:").pack(anchor="w")
        self.file_listbox = DraggableListbox(
            list_left, self._sync_files_from_listbox, selectmode=tk.SINGLE, height=12
        )
        self.file_listbox.pack(fill=tk.BOTH, expand=True, pady=(5, 0))
        self.file_listbox.bind("<Double-Button-1>", self.preview_selected)

        button_frame = tk.Frame(list_frame, width=110)
        button_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))
        button_frame.pack_propagate(False)
        self.up_button = tk.Button(button_frame, text="↑ 上移", command=lambda: self.move_file(-1))
        self.up_button.pack(fill=tk.X, pady=2)
        self.down_button = tk.Button(button_frame, text="↓ 下移", command=lambda: self.move_file(1))
        self.down_button.pack(fill=tk.X, pady=2)
        self.remove_button = tk.Button(button_frame, text="移除选中", command=self.remove_selected)
        self.remove_button.pack(fill=tk.X, pady=2)

        output_frame = tk.Frame(main_frame)
        output_frame.pack(fill=tk.X, pady=(0, 10))
        output_row = tk.Frame(output_frame)
        output_row.pack(fill=tk.X)
        tk.Label(output_row, text="输出 PDF:", width=12, anchor="w").pack(side=tk.LEFT)
        self.output_entry = tk.Entry(output_row)
        self.output_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.output_button = tk.Button(output_row, text="浏览", command=self.select_output_file)
        self.output_button.pack(side=tk.RIGHT)

        dpi_row = tk.Frame(output_frame)
        dpi_row.pack(fill=tk.X, pady=(5, 0))
        tk.Label(dpi_row, text="图片质量 DPI:", width=12, anchor="w").pack(side=tk.LEFT)
        self.dpi_entry = tk.Entry(dpi_row, width=10)
        self.dpi_entry.insert(0, "300")
        self.dpi_entry.pack(side=tk.LEFT, padx=5)
        tk.Label(dpi_row, text="72-600，推荐 300", fg="gray").pack(side=tk.LEFT)

        control_frame = tk.Frame(main_frame)
        control_frame.pack(fill=tk.X, pady=(0, 10))
        self.convert_button = tk.Button(
            control_frame,
            text="开始转换",
            command=self.start_conversion,
            bg="#4CAF50",
            fg="white",
            height=2,
        )
        self.convert_button.pack(side=tk.LEFT, padx=(0, 10))
        self.cancel_button = tk.Button(
            control_frame,
            text="取消转换",
            command=self.cancel_conversion,
            state="disabled",
        )
        self.cancel_button.pack(side=tk.LEFT)

        ttk.Progressbar(main_frame, variable=self.progress_var, maximum=100).pack(fill=tk.X)
        self.progress_label = tk.Label(main_frame, text="准备就绪")
        self.progress_label.pack(pady=(5, 0))
        self.status_label = tk.Label(main_frame, text="请选择图片文件夹", fg="gray")
        self.status_label.pack()

    def select_input_folder(self) -> None:
        folder = filedialog.askdirectory(title="选择包含图片的文件夹")
        if not folder:
            return
        self.input_folder = Path(folder)
        self._set_entry(self.input_entry, folder)
        self.files = sorted(
            (
                path
                for path in self.input_folder.iterdir()
                if path.is_file() and path.suffix.lower() in SUPPORTED_FORMATS
            ),
            key=lambda path: natural_sort_key(path.name),
        )
        self._refresh_list()
        self._set_entry(
            self.output_entry,
            str(self.input_folder / f"{self.input_folder.name}_merged.pdf"),
        )

    def select_output_file(self) -> None:
        output = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            title="保存 PDF 文件",
            filetypes=[("PDF 文件", "*.pdf")],
        )
        if output:
            self._set_entry(self.output_entry, output)

    @staticmethod
    def _set_entry(entry: tk.Entry, value: str) -> None:
        entry.delete(0, tk.END)
        entry.insert(0, value)

    def _refresh_list(self) -> None:
        self.file_listbox.delete(0, tk.END)
        for path in self.files:
            self.file_listbox.insert(tk.END, path.name)
        count = len(self.files)
        self.status_label.config(
            text=f"待转换: {count} 个文件", fg="green" if count else "gray"
        )

    def _sync_files_from_listbox(self) -> None:
        if not self.input_folder:
            return
        self.files = [
            self.input_folder / self.file_listbox.get(index)
            for index in range(self.file_listbox.size())
        ]

    def remove_selected(self) -> None:
        selection = self.file_listbox.curselection()
        if selection:
            del self.files[selection[0]]
            self._refresh_list()

    def move_file(self, offset: int) -> None:
        selection = self.file_listbox.curselection()
        if not selection:
            return
        current = selection[0]
        target = current + offset
        if not 0 <= target < len(self.files):
            return
        self.files[current], self.files[target] = self.files[target], self.files[current]
        self._refresh_list()
        self.file_listbox.selection_set(target)

    def preview_selected(self, _event=None) -> None:
        selection = self.file_listbox.curselection()
        if not selection:
            return
        image_path = self.files[selection[0]]
        try:
            with Image.open(image_path) as image:
                image.thumbnail((700, 650), Image.Resampling.LANCZOS)
                preview = image.convert("RGB")
                preview_photo = ImageTk.PhotoImage(preview)
                preview.close()
        except OSError as error:
            messagebox.showerror("预览错误", f"无法预览图片：{error}")
            return

        window = tk.Toplevel(self.root)
        window.title(f"预览 - {image_path.name}")
        label = tk.Label(window, image=preview_photo)
        label.image = preview_photo
        label.pack(expand=True)

    def start_conversion(self) -> None:
        output_text = self.output_entry.get().strip()
        if not self.files or not output_text:
            messagebox.showerror("错误", "请选择图片文件夹和输出 PDF。")
            return
        missing = [path.name for path in self.files if not path.is_file()]
        if missing:
            messagebox.showerror("文件不存在", "\n".join(missing[:8]))
            return
        try:
            dpi = int(self.dpi_entry.get())
            if not 72 <= dpi <= 600:
                raise ValueError
        except ValueError:
            messagebox.showerror("参数错误", "DPI 必须是 72-600 之间的整数。")
            return

        output = Path(output_text)
        if output.exists() and not messagebox.askyesno("确认覆盖", "输出 PDF 已存在，是否覆盖？"):
            return

        self.cancel_event.clear()
        self._set_busy(True)
        threading.Thread(
            target=self._convert_worker,
            args=(list(self.files), output, dpi),
            daemon=True,
        ).start()

    def _convert_worker(self, files: List[Path], output: Path, dpi: int) -> None:
        try:
            success, errors = convert_images_to_pdf(
                files,
                output,
                dpi,
                progress_callback=lambda current, total: self.root.after(
                    0, self._update_progress, current, total
                ),
                cancel_event=self.cancel_event,
            )
        except ConversionCancelled:
            self.root.after(0, self._conversion_finished, output, 0, [], True, None)
        except (OSError, ValueError, RuntimeError) as error:
            self.root.after(0, self._conversion_finished, output, 0, [], False, str(error))
        else:
            self.root.after(0, self._conversion_finished, output, success, errors, False, None)

    def _update_progress(self, current: int, total: int) -> None:
        self.progress_var.set(current / total * 100)
        self.progress_label.config(text=f"处理中: {current}/{total}")

    def _conversion_finished(
        self,
        output: Path,
        success: int,
        errors: List[str],
        cancelled: bool,
        fatal_error: Optional[str],
    ) -> None:
        self._set_busy(False)
        if cancelled:
            self.progress_label.config(text="转换已取消")
        elif fatal_error:
            self.progress_label.config(text="转换失败")
            messagebox.showerror("转换失败", fatal_error)
        elif errors:
            self.progress_label.config(text=f"完成：成功 {success} 页，失败 {len(errors)} 张")
            messagebox.showwarning(
                "转换完成",
                f"PDF 已生成：\n{output}\n\n以下图片失败：\n" + "\n".join(errors[:8]),
            )
        else:
            self.progress_var.set(100)
            self.progress_label.config(text=f"转换完成，共 {success} 页")
            messagebox.showinfo("成功", f"PDF 已生成：\n{output}")

    def _set_busy(self, busy: bool) -> None:
        state = tk.DISABLED if busy else tk.NORMAL
        for button in (
            self.input_button,
            self.output_button,
            self.up_button,
            self.down_button,
            self.remove_button,
            self.convert_button,
        ):
            button.config(state=state)
        self.cancel_button.config(state=tk.NORMAL if busy else tk.DISABLED)
        if busy:
            self.progress_var.set(0)
            self.progress_label.config(text="准备中...")

    def cancel_conversion(self) -> None:
        self.cancel_event.set()
        self.progress_label.config(text="正在取消...")


def main() -> None:
    root = tk.Tk()
    if canvas is None or ImageReader is None:
        root.withdraw()
        messagebox.showerror("缺少依赖", "缺少 reportlab，请先运行：pip install reportlab")
        root.destroy()
        return
    ImageToPdfApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
