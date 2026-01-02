from datetime import datetime
from tkinter import Tk, filedialog
from pathlib import Path
from typing import List, Tuple, Optional
import os
import ctypes

def select_input_file() -> List[str]:
    """选择输入文件"""
    root = Tk()
    root.withdraw()
    file_paths = filedialog.askopenfilenames(
        title="选择规则文件（txt）",
        filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
    )
    root.destroy()  # 确保窗口被正确关闭
    return list(file_paths) if file_paths else []

def load_rules(file_path: str) -> Tuple[List[str], List[str]]:
    """读取规则文件，返回(注释列表, 规则列表)"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except UnicodeDecodeError:
        # 尝试其他编码
        try:
            with open(file_path, 'r', encoding='gbk') as f:
                lines = f.readlines()
        except UnicodeDecodeError:
            raise ValueError(f"无法读取文件 {file_path}，编码格式不支持")
    except FileNotFoundError:
        raise FileNotFoundError(f"文件不存在: {file_path}")
    
    comments = []
    rules = []
    i = 0
    
    # 只取文件头部连续的注释为 comments
    while i < len(lines) and lines[i].strip().startswith('#'):
        comments.append(lines[i].strip())
        i += 1
    
    # 剩下的全是规则（只保留非注释行和非空行）
    for line in lines[i:]:
        stripped = line.strip()
        if stripped and not stripped.startswith('#'):
            rules.append(stripped)
    
    return comments, rules

def update_metadata(comments: List[str], rule_count: int) -> List[str]:
    """更新注释中的元数据"""
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
            # 跳过多余的"规则数量"注释
        else:
            updated.append(line)
    
    # 添加缺失的元数据
    if not has_update_time:
        updated.insert(0, f'# 更新时间: {now}')
    if not rule_count_written:
        updated.append(f'# 规则数量：当前共 {rule_count} 条规则')
    
    return updated

def save_clash_yaml(comments: List[str], rules: List[str], output_path: str) -> None:
    """保存 Clash YAML 格式"""
    try:
        with open(output_path, 'w', encoding='utf-8', newline='\n') as f:
            for line in comments:
                f.write(line + '\n')
            f.write('payload:\n')
            for rule in rules:
                f.write(f'  - {rule}\n')
    except IOError as e:
        raise IOError(f"无法写入Clash文件 {output_path}: {e}")

def save_surge_list(comments: List[str], rules: List[str], output_path: str) -> None:
    """保存 Surge list 格式"""
    try:
        with open(output_path, 'w', encoding='utf-8', newline='\n') as f:
            for line in comments:
                f.write(line + '\n')
            f.write('\n')  # 注释和规则之间空一行
            for rule in rules:
                f.write(rule + '\n')
    except IOError as e:
        raise IOError(f"无法写入Surge文件 {output_path}: {e}")

def process_single_file(input_file: str, output_dir: Path) -> Optional[str]:
    """处理单个文件，返回成功信息或None"""
    try:
        input_path = Path(input_file)
        input_name = input_path.stem
        
        clash_file = output_dir / f'clash_rules_{input_name}.yaml'
        surge_file = output_dir / f'surge_rules_{input_name}.list'
        
        comments, rules = load_rules(input_file)
        
        if not rules:
            return f"⚠️ {input_name}: 文件中没有找到有效规则"
        
        updated_comments = update_metadata(comments, len(rules))
        
        save_clash_yaml(updated_comments, rules, str(clash_file))
        save_surge_list(updated_comments, rules, str(surge_file))
        
        return f"✅ {input_name} ({len(rules)}条规则):\n  Clash: {clash_file}\n  Surge: {surge_file}"
        
    except Exception as e:
        return f"❌ 处理 {Path(input_file).name} 失败: {str(e)}"

def main() -> None:
    """主程序入口"""
    input_files = select_input_file()
    if not input_files:
        ctypes.windll.user32.MessageBoxW(0, "未选择文件，程序已取消。", "提示", 0)
        return
    
    # 创建输出目录
    output_dir = Path(r'D:\Documents\Github\Surge\Rule')
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        ctypes.windll.user32.MessageBoxW(
            0, f"无法创建输出目录 {output_dir}，请检查权限。", "错误", 0
        )
        return
    
    success_results = []
    error_results = []
    
    # 处理每个文件
    for input_file in input_files:
        result = process_single_file(input_file, output_dir)
        if result:
            if result.startswith("✅") or result.startswith("⚠️"):
                success_results.append(result)
            else:
                error_results.append(result)
    
    # 显示结果
    if success_results or error_results:
        message_parts = []
        
        if success_results:
            message_parts.append(f"转换完成！共处理 {len(success_results)} 个文件:\n")
            message_parts.extend(success_results)
        
        if error_results:
            if success_results:
                message_parts.append("\n\n以下文件处理失败:")
            message_parts.extend(error_results)
        
        message = "\n".join(message_parts)
        title = "转换结果" if not error_results else "转换完成（部分失败）"
        ctypes.windll.user32.MessageBoxW(0, message, title, 0)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n程序被用户中断")
    except Exception as e:
        ctypes.windll.user32.MessageBoxW(0, f"程序发生未预期错误: {str(e)}", "错误", 0)
