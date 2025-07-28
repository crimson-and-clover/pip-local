from pathlib import Path
import re
from typing import Dict, List
from packaging.specifiers import SpecifierSet, Version
from packaging.markers import Marker, default_environment

import pkginfo


def parse_package_version_str(dep: str) -> Dict[str, List[str] | str]:
    """
    解析 wheels / requirements 风格的依赖声明，返回
        {
          "package_name": str,
          "package_version": List[str] | "latest",
        }
    """
    dep = dep.strip()
    if not dep:
        raise ValueError("Empty dependency string")

    pkg_pat = re.compile(
        r"^(?P<package_name>[A-Za-z0-9_\-]+)(?:\[(?P<extra_name>[A-Za-z0-9_\-,]+)\])?"
    )
    pkg_mat = pkg_pat.match(dep)
    if pkg_mat:
        package_name = pkg_mat.group('package_name')
        extra_name = pkg_mat.group('extra_name')
        full_name = pkg_mat.group(0)
        if extra_name is None:
            extra_name = ""
    else:
        raise ValueError(f"Cannot find package name in: {dep}")

    extra = [extra_name.strip()
             for extra_name in extra_name.split(",") if extra_name.strip()]

    ver_pat = re.compile(
        r"""                   # 例:  (==1.2.3)  >=1.0   <2.0,>=1.5
        [\s(]*             # 前导空白或左括号
        (?P<constraint>    # 捕获整个约束串
            (?:==|!=|~=|>=|<=|>|<)\s*[^,)\s]+  # 单个约束
            (?:\s*,\s*(?:==|!=|~=|>=|<=|>|<)\s*[^,)\s]+)*  # 后续约束
        )
        [\s)]*             # 尾随空白或右括号
        """,
        re.VERBOSE,
    )

    # 2️⃣ 查找版本约束（可能在括号内，也可能直接跟在包名后）
    version_match = ver_pat.search(dep[len(full_name):])
    if version_match:
        constraints_str = version_match.group("constraint")
        ver_spec = SpecifierSet(constraints_str)
    else:
        ver_spec = SpecifierSet()

    # print(f"{dep} -> '{package_name}' '{extra}' '{ver_spec}'")
    return package_name, extra, ver_spec


def parse_wheels_dependency(filepath: Path) -> dict:
    whl = pkginfo.wheel.Wheel(filepath)
    deps_str = whl.requires_dist
    py_dep = whl.requires_python
    if py_dep is None:
        py_dep = ""
    py_dep = SpecifierSet(py_dep)

    pkg_deps = []
    for dep in deps_str:
        dep_sep = list(map(lambda x: x.strip(), dep.split(";")))
        parse_result = {
            "package_name": "",
            "package_extra": [],
            "package_version": "",
            "package_markers": [],
        }
        for i, s in enumerate(dep_sep):
            if i == 0:
                pkg_name, extra, ver_spec = parse_package_version_str(s)
                parse_result["package_name"] = pkg_name
                parse_result["package_extra"] = extra
                parse_result["package_version"] = ver_spec
            else:
                parse_result["package_markers"].append(Marker(s))
        assert parse_result["package_name"] != ""
        pkg_deps.append(parse_result)

    return py_dep, pkg_deps


if __name__ == "__main__":
    wheels_dir = Path("wheels")
    ss = set()
    from python_environment import get_python_environment
    from packaging.markers import Marker, default_environment
    env = default_environment()
    # env["extra"] = "test"
    # marker = Marker("extra == 'test'; python_version == '3.10'")
    # print(marker.evaluate(env))

    whl = Path("wheels/torch-2.7.1+cu118-cp310-cp310-manylinux_2_28_x86_64.whl")
    py_dep, pkg_deps = parse_wheels_dependency(whl)
    print(f"py_dep: '{py_dep}'")
    print(f"pkg_deps: '{pkg_deps}'")
    print(SpecifierSet(py_dep).contains(Version("1.1")))

    # for wheel_file in wheels_dir.glob("*.whl"):
    #     whl = pkginfo.wheel.Wheel(wheel_file)
    #     requires_dist = whl.requires_dist
    #     for dep in requires_dist:
    #         dep_sep = list(map(lambda x: x.strip(), dep.split(";")))
    #         parse_wheels_dependency_str0(dep_sep[0])
    # for s in dep_sep[1:]:
    #     marker = Marker(s)
    #     print(f"{s} -> {marker.evaluate(env)}")
