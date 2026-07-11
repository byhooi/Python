"""尝试不同字段组合，检查目标 Mkey 的摘要算法。"""

import hashlib
from typing import Iterable, Tuple


TOKEN = "WeixinMiniToken:719:31d6349f167d348af24758ea91c15dda10bb9e31"
URL = "/clientApi/signInRecordAdd"
TIMESTAMP = "1724124247"
OPENID = "ol4uQ5A8FEN8DFT3augaZ74KydhM"
VERSION = "4.11.23"
TARGET_MKEY = "18ab155377daad3869d42b6ed4837837"


def generate_mkey_sha1(data: str) -> str:
    return hashlib.sha1(data.encode("utf-8")).hexdigest()


def generate_mkey_md5(data: str) -> str:
    return hashlib.md5(data.encode("utf-8")).hexdigest()


def build_combinations() -> Tuple[str, ...]:
    """生成待验证的字段组合。

    每项均显式分隔，避免相邻 f-string 被 Python 自动拼接。
    """
    return (
        f"{TIMESTAMP}.{TOKEN}.{OPENID}",
        f"{TOKEN}{OPENID}{TIMESTAMP}",
        f"{TOKEN}{TIMESTAMP}{OPENID}",
        f"{URL}{TOKEN}{TIMESTAMP}",
        f"{OPENID}{TOKEN}{TIMESTAMP}{VERSION}",
        f"{TOKEN}{URL}{OPENID}{TIMESTAMP}{VERSION}",
        f"{TOKEN}{TIMESTAMP}",
        f"{TIMESTAMP}{TOKEN}",
    )


def print_results(title: str, values: Iterable[str], algorithm: str) -> None:
    """计算并输出一组候选结果。"""
    print(title)
    for index, data in enumerate(values, 1):
        if algorithm == "sha1":
            digest = generate_mkey_sha1(data)[:32]
        else:
            digest = generate_mkey_md5(data)
        print(f"组合 {index}: {digest}  匹配: {digest == TARGET_MKEY}")


def main() -> None:
    combinations = build_combinations()
    print_results("使用 SHA-1:", combinations, "sha1")
    print()
    print_results("使用 MD5:", combinations, "md5")


if __name__ == "__main__":
    main()
