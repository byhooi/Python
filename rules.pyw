import os
import ctypes
from datetime import datetime
from tkinter import Tk, filedialog

# 选择输入文件
def select_input_file():
    root = Tk()
    root.withdraw()
    file_path = filedialog.askopenfilename(
        title="选择规则文件（txt）",
        filetypes=[("Text files", "*.txt")]
    )
    return file_path

# 读取规则
def load_rules(file_path):
    comments = []
    rules = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            stripped = line.strip()
            if stripped.startswith('#'):
                comments.append(stripped)
            elif stripped:
                rules.append(stripped)
    return comments, rules

# 更新注释中的元数据
def update_metadata(comments, rule_count):
    updated = []
    now = datetime.now().strftime('%Y/%m/%d %H:%M:%S')
    for line in comments:
        if '更新时间' in line:
            updated.append(f'# 更新时间: {now}')
        elif '规则数量' in line:
            updated.append(f'# 规则数量：当前共 {rule_count} 条规则')
        else:
            updated.append(line)
    return updated

# 保存 Clash YAML 格式
def save_clash_yaml(comments, rules, output_path):
    with open(output_path, 'w', encoding='utf-8') as f:
        for line in comments:
            f.write(line + '\n')
        f.write('payload:\n')
        for rule in rules:
            f.write(f'  - {rule}\n')

# 保存 Surge list 格式
def save_surge_list(comments, rules, output_path):
    with open(output_path, 'w', encoding='utf-8') as f:
        for line in comments:
            f.write(line + '\n')
        for rule in rules:
            f.write(rule + '\n')

# 主程序入口
def main():
    input_file = select_input_file()
    if not input_file:
        ctypes.windll.user32.MessageBoxW(0, "未选择文件，程序已取消。", "提示", 0)
        return

    # 取文件名用于输出命名
    input_name = os.path.splitext(os.path.basename(input_file))[0]

    # 输出路径
    output_dir = r'D:\Github\Surge\Rule'
    os.makedirs(output_dir, exist_ok=True)
    clash_file = os.path.join(output_dir, f'clash_rules_{input_name}.yaml')
    surge_file = os.path.join(output_dir, f'surge_rules_{input_name}.list')

    try:
        comments, rules = load_rules(input_file)
        updated_comments = update_metadata(comments, len(rules))

        save_clash_yaml(updated_comments, rules, clash_file)
        save_surge_list(updated_comments, rules, surge_file)

        message = f"转换完成！\n\nClash:\n{clash_file}\n\nSurge:\n{surge_file}"
        ctypes.windll.user32.MessageBoxW(0, message, "成功", 0)

    except Exception as e:
        ctypes.windll.user32.MessageBoxW(0, f"发生错误: {str(e)}", "错误", 0)

if __name__ == '__main__':
    main()
