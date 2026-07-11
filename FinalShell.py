"""FinalShell 离线激活码计算工具。"""

import hashlib
from typing import Dict

try:
    from Crypto.Hash import keccak
except ModuleNotFoundError:
    keccak = None


def md5_hex(message: bytes) -> str:
    """计算 MD5 十六进制摘要。"""
    return hashlib.md5(message).hexdigest()


def keccak384_hex(message: bytes) -> str:
    """计算 Keccak-384 十六进制摘要。"""
    if keccak is None:
        raise RuntimeError("缺少 pycryptodome，请先运行：pip install pycryptodome")
    return keccak.new(data=message, digest_bits=384).hexdigest()


def generate_codes(machine_code: str) -> Dict[str, str]:
    """根据机器码生成新旧版本的高级版和专业版激活码。"""
    code = machine_code.strip()
    if not code:
        raise ValueError("机器码不能为空")

    return {
        "旧版高级版": md5_hex(f"61305{code}8552".encode("utf-8"))[8:24],
        "旧版专业版": md5_hex(f"2356{code}13593".encode("utf-8"))[8:24],
        "新版高级版": keccak384_hex(f"{code}hSf(78cvVlS5E".encode("utf-8"))[12:28],
        "新版专业版": keccak384_hex(f"{code}FF3Go(*Xvbb5s2".encode("utf-8"))[12:28],
    }


def main() -> int:
    """运行命令行交互。"""
    try:
        codes = generate_codes(input("输入机器码: "))
    except (EOFError, KeyboardInterrupt):
        print("\n操作已取消。")
        return 130
    except (RuntimeError, ValueError) as error:
        print(f"错误: {error}")
        return 1

    print("版本号 < 3.9.6（旧版）")
    print("高级版:", codes["旧版高级版"])
    print("专业版:", codes["旧版专业版"])
    print("版本号 >= 3.9.6（新版）")
    print("高级版:", codes["新版高级版"])
    print("专业版:", codes["新版专业版"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
