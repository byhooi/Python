from datetime import datetime
from tkinter import Tk, filedialog
import os
import ctypes

# 选择输入文件
def select_input_file():
    root = Tk()
    root.withdraw()
    file_paths = filedialog.askopenfilenames(
        title="选择规则文件（txt）",
        filetypes=[("Text files", "*.txt")]
    )
    return file_paths

# 读取规则
def load_rules(file_path):
    comments = []
    rules = []
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    i = 0
    # 只取文件头部连续的注释为 comments
    while i < len(lines) and lines[i].strip().startswith('#'):
        comments.append(lines[i].strip())
        i += 1
    # 剩下的全是规则（只保留非注释行）
    for line in lines[i:]:
        stripped = line.strip()
        if stripped and not stripped.startswith('#'):
            rules.append(stripped)
    return comments, rules

# 更新注释中的元数据
def update_metadata(comments, rule_count):
    updated = []
    now = datetime.now().strftime('%Y/%m/%d %H:%M:%S')
    has_update_time = False
    rule_count_written = False
    for line in comments:
        if '更新时间' in line:
            updated.append(f'# 更新时间: {now}')
            has_update_time = True
        elif '规则数量' in line:
            if not rule_count_written:
                updated.append(f'# 规则数量：当前共 {rule_count} 条规则')
                rule_count_written = True
            # 跳过多余的“规则数量”注释
        else:
            updated.append(line)
    if not has_update_time:
        updated.insert(0, f'# 更新时间: {now}')
    if not rule_count_written:
        updated.append(f'# 规则数量：当前共 {rule_count} 条规则')
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
        f.write('\n')  # 注释和规则之间空一行
        for rule in rules:
            f.write(rule + '\n')

# 主程序入口
def main():
    input_files = select_input_file()
    if not input_files:
        ctypes.windll.user32.MessageBoxW(0, "未选择文件，程序已取消。", "提示", 0)
        return

    output_dir = r'D:\Github\Surge\Rule'
    os.makedirs(output_dir, exist_ok=True)
    
    success_files = []
    for input_file in input_files:
        try:
            # 取文件名用于输出命名
            input_name = os.path.splitext(os.path.basename(input_file))[0]
            
            clash_file = os.path.join(output_dir, f'clash_rules_{input_name}.yaml')
            surge_file = os.path.join(output_dir, f'surge_rules_{input_name}.list')

            comments, rules = load_rules(input_file)
            updated_comments = update_metadata(comments, len(rules))

            save_clash_yaml(updated_comments, rules, clash_file)
            save_surge_list(updated_comments, rules, surge_file)
            
            success_files.append(f"\n{input_name}:\nClash: {clash_file}\nSurge: {surge_file}")

        except Exception as e:
            ctypes.windll.user32.MessageBoxW(0, f"处理文件 {input_file} 时发生错误: {str(e)}", "错误", 0)
            continue

    if success_files:
        message = "转换完成！" + "\n".join(success_files)
        ctypes.windll.user32.MessageBoxW(0, message, "成功", 0)

if __name__ == '__main__':
    main()
