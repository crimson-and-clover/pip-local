import json
from pathlib import Path
import sysconfig
from typing import List

from packaging.tags import (
    Tag,
    compatible_tags,
    cpython_tags,
    interpreter_name,
    interpreter_version,
    platform_tags,
    sys_tags,
)


def dump_platforms():
    platform_dir = Path("platforms")
    platform_dir.mkdir(parents=True, exist_ok=True)
    p_t = list(platform_tags())
    platform_file = platform_dir / \
        f"{sysconfig.get_platform().replace('-', '_').strip()}.json"
    with platform_file.open("w", encoding="utf-8") as f:
        json.dump(p_t, f, indent=4)


def load_linux_x86_64_platforms() -> List[str]:
    with Path("platforms/linux_x86_64.json").open("r", encoding="utf-8") as f:
        return json.load(f)


def get_compat_wheel_tags(py_ver_str: str, plat_tags: List[str]) -> List[str]:
    py_ver = tuple(map(int, py_ver_str.split(".")[0:2]))
    cpy_tags = list(cpython_tags(
        python_version=py_ver, platforms=plat_tags))
    py_tags = list(compatible_tags(
        python_version=py_ver,
        interpreter=f"cp{py_ver[0]}{py_ver[1]}", platforms=plat_tags))
    return cpy_tags + py_tags


if __name__ == "__main__":
    dump_platforms()
    tags = get_compat_wheel_tags("3.9", load_linux_x86_64_platforms())
    for t in tags:
        print(t)
