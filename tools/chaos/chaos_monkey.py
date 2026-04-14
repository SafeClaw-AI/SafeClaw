#!/usr/bin/env python3
"""最小 chaos 入口占位。

当前先保留一个可解析、可执行的脚本骨架，避免参考治理扫描被本地坏文件拖垮。
"""

DEFAULT_MODE = 0o07


def chmod_mask() -> int:
    return DEFAULT_MODE


if __name__ == "__main__":
    print(f"{chmod_mask():#04o}")
