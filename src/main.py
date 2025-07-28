from copy import deepcopy
from functools import reduce
from pathlib import Path
import re
import shutil
import tempfile
from typing import Callable
from typing import Dict, List

from bs4 import BeautifulSoup
from packaging.tags import sys_tags
from packaging.version import Version, InvalidVersion
from packaging.specifiers import SpecifierSet, InvalidSpecifier
import pkginfo
import requests
from tqdm import tqdm
from wheel_index import get_wheel_index, get_suitable_package
from python_environment import get_python_environment
from wheel_tags import get_compat_wheel_tags, load_linux_x86_64_platforms
from wheel_parse import parse_wheels_dependency, parse_package_version_str
from downloader import download_package


def check_package_dependency(pkg_dep: Dict, extra: List[str], py_env: Dict) -> bool:
    pkg_markers = pkg_dep["package_markers"]
    if len(extra) == 0:
        extra = [""]
    for marker in pkg_markers:
        result = reduce(lambda x, y: x or y,
                        map(lambda e: marker.evaluate({**py_env, "extra": e}), extra))
        if not result:
            return False
    return True


if __name__ == "__main__":
    # input
    req = {
        "torch": "==2.5.1+cu118"
    }
    py_ver = "3.12"

    # process
    new_req = {}
    for k, v in req.items():
        pkg_name, extra, _ = parse_package_version_str(k)
        if v == "latest":
            ver_spec = SpecifierSet()
        else:
            ver_spec = SpecifierSet(v)
        new_req[pkg_name] = {"package_extra": extra,
                             "package_version": ver_spec}

    compat_tags = get_compat_wheel_tags(py_ver, load_linux_x86_64_platforms())
    py_env = get_python_environment(py_ver)
    py_ver = Version(py_ver)

    # download root package
    req_pkg_names = list(new_req.keys())
    dep_pkg_names = []
    for pkg_name in req_pkg_names:
        pkg_spec = new_req[pkg_name]
        pkg_index = get_wheel_index(pkg_name)
        best_match, candidate = get_suitable_package(
            pkg_name, pkg_index, ver_spec, compat_tags)
        pkg_path = download_package(best_match)
        if pkg_path.suffix == ".whl":
            py_dep, pkg_deps = parse_wheels_dependency(pkg_path)
            if not py_dep.contains(py_ver):
                raise ValueError(
                    f"Package requires python version {py_dep}, but current python version is {py_env}")
            req_deps = []
            for pkg_dep in pkg_deps:
                if check_package_dependency(pkg_dep, pkg_spec["package_extra"], py_env):
                    req_deps.append(pkg_dep)

            print(
                f"Package {pkg_name} {best_match['package_version']} requires:")
            for dep in req_deps:
                dep_name = dep["package_name"]
                dep_extra = dep["package_extra"]
                dep_ver = dep["package_version"]
                dep_pkg_names.append(dep_name)
                print(
                    f"\t{dep_name} {dep_ver}")

                if dep_name in new_req:
                    new_req[dep_name]["package_extra"] = list(
                        set(new_req[dep_name]["package_extra"] + dep_extra))
                    new_req[dep_name]["package_version"] &= dep_ver
                else:
                    new_req[dep_name] = {
                        "package_extra": dep_extra,
                        "package_version": dep_ver
                    }
            print()

    # download dependency packages
    while len(dep_pkg_names) > 0:
        pkg_name = dep_pkg_names.pop(0)
        pkg_spec = new_req[pkg_name]["package_version"]
        pkg_extra = new_req[pkg_name]["package_extra"]
        pkg_index = get_wheel_index(pkg_name)
        best_match, candidate = get_suitable_package(
            pkg_name, pkg_index, pkg_spec, compat_tags)

        while True:
            pkg_path = download_package(best_match)
            py_dep, pkg_deps = parse_wheels_dependency(pkg_path)
            if not py_dep.contains(py_ver):
                print(
                    f"Package {pkg_name} {pkg_spec} requires python version {py_dep}, but current python version is {py_ver}, try next version")
                best_match = candidate.pop(-1)
                continue

            req_deps = []
            for pkg_dep in pkg_deps:
                if check_package_dependency(pkg_dep, pkg_extra, py_env):
                    req_deps.append(pkg_dep)

            print(
                f"Package {pkg_name} {best_match['package_version']} requires:")
            for dep in req_deps:
                dep_name = dep["package_name"]
                dep_extra = dep["package_extra"]
                dep_ver = dep["package_version"]
                dep_pkg_names.append(dep_name)
                print(
                    f"\t{dep_name} {dep_ver}")

                if dep_name in new_req:
                    new_req[dep_name]["package_extra"] = list(
                        set(new_req[dep_name]["package_extra"] + dep_extra))
                    new_req[dep_name]["package_version"] &= dep_ver
                else:
                    new_req[dep_name] = {
                        "package_extra": dep_extra,
                        "package_version": dep_ver
                    }
            print()
            break

    pass
