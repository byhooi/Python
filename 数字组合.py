import random
from pathlib import Path
from tempfile import NamedTemporaryFile


def build_easy_pins_pool() -> set[str]:
    """构建容易记忆的 6 位数字候选池"""
    pool = set()
    digits = [str(i) for i in range(10)]

    # 1. 模式 ABCABC (如 168168, 520520)
    for a in digits:
        for b in digits:
            for c in digits:
                if len({a, b, c}) > 1:  # 排除全相同的 111111
                    pool.add(f"{a}{b}{c}{a}{b}{c}")

    # 2. 模式 ABABAB (如 282828, 696969)
    for a in digits:
        for b in digits:
            if a != b:
                pool.add(f"{a}{b}{a}{b}{a}{b}")

    # 3. 模式 AABBCC (如 112233, 668899)
    for a in digits:
        for b in digits:
            for c in digits:
                if a != b and b != c:
                    pool.add(f"{a}{a}{b}{b}{c}{c}")

    # 4. 模式 AAABBB (如 888666, 111999)
    for a in digits:
        for b in digits:
            if a != b:
                pool.add(f"{a*3}{b*3}")

    # 5. 镜像回文 ABCCBA (如 123321, 689986)
    for a in digits:
        for b in digits:
            for c in digits:
                if len({a, b, c}) > 1:
                    pool.add(f"{a}{b}{c}{c}{b}{a}")

    # 6. 等差等步长数列 (如 135791, 024680, 975319)
    for start in range(10):
        for step in [2, 3]:
            # 递增循环
            seq_up = "".join(str((start + i * step) % 10) for i in range(6))
            # 递减循环
            seq_down = "".join(str((start - i * step) % 10) for i in range(6))
            pool.add(seq_up)
            pool.add(seq_down)

    return pool


def read_generated_pins(path: Path) -> set[str]:
    """兼容纯数字和 .xyz 域名记录，统一提取数字部分并保留前导零。"""
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except FileNotFoundError:
        return set()

    pins = set()
    for line_number, line in enumerate(lines, start=1):
        pin = line.strip()
        if not pin:
            continue
        pin = pin.lower().removesuffix(".xyz")
        if len(pin) != 6 or not pin.isascii() or not pin.isdecimal():
            raise ValueError(f"{path} 第 {line_number} 行不是有效的 6 位数字或 .xyz 域名")
        pins.add(pin)
    return pins


def save_pins(path: Path, pins: list[str]) -> None:
    """先写同目录临时文件再替换，避免写入失败破坏已有记录。"""
    temporary_path = None
    try:
        with NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent,
            prefix=f".{path.name}.", suffix=".tmp", delete=False,
        ) as file:
            temporary_path = Path(file.name)
            file.write("\n".join(pins) + "\n")
        temporary_path.replace(path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def generate_100_easy_pins(output_file: str | Path = "easy_pins.txt") -> list[str]:
    """生成并返回 100 个六位数字 .xyz 域名，不与同一输出路径的历史重复。"""
    output_path = Path(output_file)
    history_path = output_path.with_name(f"{output_path.stem}_history.txt")
    # 同时读取旧输出，首次升级时也能避开已有的 100 组号码。
    used_pins = read_generated_pins(history_path) | read_generated_pins(output_path)
    available_pins = sorted(build_easy_pins_pool() - used_pins)
    if len(available_pins) < 100:
        raise ValueError(
            f"未使用的数字组合只剩 {len(available_pins)} 组，不足 100 组；"
            "为避免重复，本次未生成，原文件保持不变。"
        )

    selected_100 = random.sample(available_pins, 100)
    domains = [f"{pin}.xyz" for pin in selected_100]

    # 先保留历史再发布结果，输出写入失败时宁可少用号码，也不重复使用。
    save_pins(history_path, sorted(used_pins | set(selected_100)))
    save_pins(output_path, domains)
    for domain in domains:
        print(domain)

    return domains


if __name__ == "__main__":
    try:
        generate_100_easy_pins()
    except (OSError, ValueError) as error:
        raise SystemExit(f"生成失败：{error}") from error
