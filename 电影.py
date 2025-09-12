import os
import re
from pathlib import Path
from typing import List, Tuple, Optional


def validate_url(url: str) -> bool:
    """验证URL格式是否正确"""
    url_pattern = re.compile(
        r'^https?://'  # http:// 或 https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # 域名
        r'localhost|'  # localhost
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # IP地址
        r'(?::\d+)?'  # 可选端口
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    return url_pattern.match(url) is not None


def parse_video_input(input_str: str) -> Optional[Tuple[str, str]]:
    """解析视频输入格式，返回(标题, 链接)元组"""
    input_str = input_str.strip()
    if not input_str:
        return None
    
    # 尝试空格分割
    if ' ' in input_str:
        parts = input_str.rsplit(' ', 1)
        title, link = parts[0].strip(), parts[1].strip()
        if validate_url(link):
            return title, link
    
    # 尝试$分割
    if '$' in input_str:
        parts = input_str.rsplit('$', 1)
        title, link = parts[0].strip(), parts[1].strip()
        if validate_url(link):
            return title, link
    
    return None


def create_m3u8_file(videos: List[Tuple[str, str]], file_path: Path) -> None:
    """创建M3U8播放列表文件"""
    try:
        with open(file_path, 'w', encoding='utf-8', newline='\n') as f:
            f.write('#EXTM3U\n\n')
            for title, link in videos:
                f.write(f'#EXTINF:-1,{title}\n{link}\n\n')
    except IOError as e:
        raise IOError(f"无法写入文件 {file_path}: {e}")


def get_playlist_name() -> Optional[str]:
    """获取播放列表名称"""
    while True:
        name = input("请输入播放列表的名称（不需要扩展名），输入 'q' 退出程序: ").strip()
        if name.lower() == 'q':
            return None
        
        if not name:
            return "playlist"
        
        # 验证文件名
        invalid_chars = '<>:"/\\|?*'
        if any(char in name for char in invalid_chars):
            print(f"文件名不能包含以下字符: {invalid_chars}")
            continue
        
        return name


def collect_videos() -> List[Tuple[str, str]]:
    """收集视频信息"""
    print("请输入视频链接，格式为 '标题 https://链接' 或 '标题$https://链接'，直接回车结束。")
    videos = []
    
    while True:
        input_str = input(f"第{len(videos)+1}个视频: " if videos else "视频链接: ")
        if not input_str.strip():
            break
        
        parsed = parse_video_input(input_str)
        if parsed:
            videos.append(parsed)
            print(f"✓ 已添加: {parsed[0]}")
        else:
            print("❌ 输入格式错误，请使用 '标题 链接' 或 '标题$链接' 格式，且链接需要是有效的URL")
    
    return videos


def main():
    """主函数"""
    default_save_dir = Path(r"D:\movie")
    
    try:
        default_save_dir.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        print(f"无法创建目录 {default_save_dir}，请检查权限")
        return
    
    print(f"播放列表将保存到: {default_save_dir}")
    
    while True:
        playlist_name = get_playlist_name()
        if playlist_name is None:  # 用户选择退出
            break
        
        videos = collect_videos()
        
        if not videos:
            print("未输入任何有效的视频链接！")
            continue
        
        file_path = default_save_dir / f"{playlist_name}.m3u8"
        
        try:
            create_m3u8_file(videos, file_path)
            print(f"✓ 播放列表已创建: {file_path}")
            print(f"  包含 {len(videos)} 个视频")
        except IOError as e:
            print(f"❌ 创建播放列表失败: {e}")
        
        print("\n" + "="*50 + "\n")

if __name__ == "__main__":
    main()
