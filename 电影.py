import argparse
from pathlib import Path
from typing import List, Optional, Tuple
from urllib.parse import urlsplit


DEFAULT_SAVE_DIR = Path(r"D:\Videos")
INVALID_FILENAME_CHARS = frozenset('<>:"/\\|?*')
WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{number}" for number in range(1, 10)),
    *(f"LPT{number}" for number in range(1, 10)),
}

Video = Tuple[str, str]


def validate_url(url: str) -> bool:
    """验证是否为格式完整的 HTTP(S) URL。"""
    if not url or any(char.isspace() for char in url):
        return False

    try:
        parsed = urlsplit(url)
        # 访问 port 属性时还会校验端口格式和范围。
        parsed.port
    except ValueError:
        return False

    return parsed.scheme.lower() in {"http", "https"} and parsed.hostname is not None


def parse_video_input(input_str: str) -> Optional[Video]:
    """解析“标题 URL”或“标题$URL”，返回（标题, URL）。"""
    value = input_str.strip()
    if not value:
        return None

    # “$”是明确分隔符，优先处理；rsplit 可保留标题内的空格或“$”。
    if "$" in value:
        title, link = value.rsplit("$", 1)
        title, link = title.strip(), link.strip()
        if title and validate_url(link):
            return title, link

    try:
        title, link = value.rsplit(maxsplit=1)
    except ValueError:
        return None

    title, link = title.strip(), link.strip()
    if title and validate_url(link):
        return title, link
    return None


def create_m3u8_file(videos: List[Video], file_path: Path) -> None:
    """以原子替换方式创建 UTF-8 编码的 M3U8 播放列表。"""
    temp_path = file_path.with_name(f".{file_path.name}.tmp")

    try:
        with temp_path.open("w", encoding="utf-8", newline="\n") as file:
            file.write("#EXTM3U\n")
            for title, link in videos:
                # 避免换行符破坏 M3U8 的行结构。
                safe_title = " ".join(title.splitlines()).strip()
                file.write(f"\n#EXTINF:-1,{safe_title}\n{link}\n")
        temp_path.replace(file_path)
    except OSError as error:
        try:
            temp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise OSError(f"无法写入文件 {file_path}: {error}") from error


def validate_playlist_name(name: str) -> Optional[str]:
    """返回播放列表基础文件名；无效时返回 None。"""
    if name.lower().endswith(".m3u8"):
        name = name[:-5].rstrip()

    if (
        not name
        or name in {".", ".."}
        or name[-1] in {" ", "."}
        or any(char in INVALID_FILENAME_CHARS or ord(char) < 32 for char in name)
    ):
        return None

    base_name = name.split(".", 1)[0].upper()
    if base_name in WINDOWS_RESERVED_NAMES:
        return None
    return name


def get_playlist_name() -> Optional[str]:
    """获取播放列表名称；输入 q 时返回 None。"""
    while True:
        name = input(
            "请输入播放列表名称（无需扩展名，直接回车使用 playlist，输入 q 退出）: "
        ).strip()
        if name.casefold() == "q":
            return None
        if not name:
            return "playlist"

        validated_name = validate_playlist_name(name)
        if validated_name is not None:
            return validated_name

        print(
            "文件名无效：不能包含控制字符或 "
            f"{''.join(sorted(INVALID_FILENAME_CHARS))}，不能以空格或句点结尾，"
            "也不能使用 Windows 保留名称。"
        )


def collect_videos() -> List[Video]:
    """持续收集视频信息，直接回车时结束。"""
    print("请输入视频，格式为“标题 https://链接”或“标题$https://链接”，直接回车结束。")
    videos: List[Video] = []

    while True:
        prompt = f"第 {len(videos) + 1} 个视频: "
        input_str = input(prompt)
        if not input_str.strip():
            return videos

        parsed = parse_video_input(input_str)
        if parsed is None:
            print("[错误] 输入无效，请检查标题、分隔符及 HTTP(S) 链接。")
            continue

        videos.append(parsed)
        print(f"[成功] 已添加: {parsed[0]}")


def parse_args() -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(description="交互式创建 M3U8 视频播放列表")
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=DEFAULT_SAVE_DIR,
        help=f"播放列表保存目录（默认: {DEFAULT_SAVE_DIR}）",
    )
    return parser.parse_args()


def main() -> int:
    """运行交互式播放列表生成器。"""
    save_dir = parse_args().output_dir.expanduser().resolve()

    try:
        save_dir.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        print(f"无法创建保存目录 {save_dir}: {error}")
        return 1

    print(f"播放列表将保存到: {save_dir}")

    try:
        while True:
            playlist_name = get_playlist_name()
            if playlist_name is None:
                print("已退出。")
                return 0

            videos = collect_videos()
            if not videos:
                print("未输入任何有效的视频链接。")
                continue

            file_path = save_dir / f"{playlist_name}.m3u8"
            try:
                create_m3u8_file(videos, file_path)
            except OSError as error:
                print(f"[错误] 创建播放列表失败: {error}")
            else:
                print(f"[成功] 播放列表已创建: {file_path}")
                print(f"  包含 {len(videos)} 个视频")

            print(f"\n{'=' * 50}\n")
    except (EOFError, KeyboardInterrupt):
        print("\n操作已取消。")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
