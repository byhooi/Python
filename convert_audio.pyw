import tkinter as tk
from tkinter import filedialog, messagebox
import subprocess
import threading
import os
import sys

class AudioConverterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Audio to MP3 Converter")
        self.root.geometry("600x400")

        # Files list
        self.files = []

        # UI Elements
        self.create_widgets()

    def create_widgets(self):
        # Top Frame for Buttons
        top_frame = tk.Frame(self.root, pady=10)
        top_frame.pack(fill=tk.X, padx=10)

        self.btn_add = tk.Button(top_frame, text="Add Files", command=self.add_files, bg="#dddddd", padx=10)
        self.btn_add.pack(side=tk.LEFT, padx=5)

        self.btn_clear = tk.Button(top_frame, text="Clear List", command=self.clear_list, padx=10)
        self.btn_clear.pack(side=tk.LEFT, padx=5)

        self.btn_convert = tk.Button(top_frame, text="Start Conversion to MP3", command=self.start_conversion_thread, bg="#4CAF50", fg="white", padx=10, font=("Arial", 10, "bold"))
        self.btn_convert.pack(side=tk.RIGHT, padx=5)

        # Listbox to show selected files
        self.listbox_frame = tk.Frame(self.root)
        self.listbox_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.scrollbar = tk.Scrollbar(self.listbox_frame)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.file_listbox = tk.Listbox(self.listbox_frame, yscrollcommand=self.scrollbar.set, selectmode=tk.EXTENDED)
        self.file_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.config(command=self.file_listbox.yview)

        # Status Area
        self.status_var = tk.StringVar()
        self.status_var.set("Ready")
        self.status_label = tk.Label(self.root, textvariable=self.status_var, bd=1, relief=tk.SUNKEN, anchor=tk.W)
        self.status_label.pack(side=tk.BOTTOM, fill=tk.X)

    def add_files(self):
        filetypes = (
            ("Audio Files", "*.m4a *.wav *.flac *.wma *.aac *.ogg"),
            ("All Files", "*.*")
        )
        filenames = filedialog.askopenfilenames(title="Select Audio Files", filetypes=filetypes)
        if filenames:
            for f in filenames:
                if f not in self.files:
                    self.files.append(f)
                    self.file_listbox.insert(tk.END, f)
            self.status_var.set(f"Added {len(filenames)} file(s). Total: {len(self.files)}")

    def clear_list(self):
        self.files = []
        self.file_listbox.delete(0, tk.END)
        self.status_var.set("List cleared.")

    def start_conversion_thread(self):
        if not self.files:
            messagebox.showwarning("No Files", "Please add files to convert first.")
            return
        
        # Disable buttons during conversion
        self.btn_add.config(state=tk.DISABLED)
        self.btn_clear.config(state=tk.DISABLED)
        self.btn_convert.config(state=tk.DISABLED)

        thread = threading.Thread(target=self.convert_files)
        thread.daemon = True
        thread.start()

    def convert_files(self):
        total = len(self.files)
        success_count = 0
        error_count = 0

        # Check for ffmpeg
        try:
            subprocess.run(["ffmpeg", "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
             self.root.after(0, lambda: messagebox.showerror("FFmpeg Not Found", "FFmpeg was not found in your system PATH.\nPlease install FFmpeg and make sure it is added to your environment variables."))
             self.root.after(0, self.reset_ui)
             return

        for idx, input_file in enumerate(self.files):
            # Update status
            msg = f"Converting ({idx+1}/{total}): {os.path.basename(input_file)}..."
            self.root.after(0, self.status_var.set, msg)

            try:
                # Prepare output filename
                path_obj = os.path.splitext(input_file)[0]
                output_file = f"{path_obj}.mp3"
                
                # FFmpeg command: High quality VBR MP3
                # -y = overwrite without asking
                # -loglevel error = less output noise
                cmd = [
                    "ffmpeg", 
                    "-i", input_file, 
                    "-c:a", "libmp3lame", 
                    "-q:a", "2", 
                    "-y",
                    "-loglevel", "error",
                    output_file
                ]
                
                # Setup startupinfo to hide console window on Windows
                startupinfo = None
                if os.name == 'nt':
                    startupinfo = subprocess.STARTUPINFO()
                    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

                subprocess.run(cmd, check=True, startupinfo=startupinfo)
                success_count += 1
            except Exception as e:
                print(f"Error converting {input_file}: {e}")
                error_count += 1
        
        # Finished
        final_msg = f"Conversion Finished. Success: {success_count}, Errors: {error_count}"
        self.root.after(0, self.status_var.set, final_msg)
        self.root.after(0, lambda: messagebox.showinfo("Done", final_msg))
        self.root.after(0, self.reset_ui)

    def reset_ui(self):
        self.btn_add.config(state=tk.NORMAL)
        self.btn_clear.config(state=tk.NORMAL)
        self.btn_convert.config(state=tk.NORMAL)


if __name__ == "__main__":
    root = tk.Tk()
    # Attempt to set icon if available, or just ignore
    # root.iconbitmap("icon.ico") 
    app = AudioConverterApp(root)
    root.mainloop()
