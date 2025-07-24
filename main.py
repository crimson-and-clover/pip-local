from typing import Callable
import pkginfo
import requests
from bs4 import BeautifulSoup
from packaging.version import Version
import concurrent.futures
import tempfile
import shutil
import os
from pathlib import Path
import time
from copy import deepcopy
from tqdm import tqdm
import re

INDEX_URL = "https://mirrors.aliyun.com/pypi/simple/"
TORCH_FIND_LINKS_CU118 = "https://mirrors.aliyun.com/pytorch-wheels/cu118/"
TORCH_FIND_LINKS_CU126 = "https://mirrors.aliyun.com/pytorch-wheels/cu126/"
TORCH_FIND_LINKS_CU128 = "https://mirrors.aliyun.com/pytorch-wheels/cu128/"


PYTHON_VERSIONS = ["3.10", "3.11", "3.12", "3.13"]

REQUIRED_PACKAGES = {
    "numpy": ["<2.0.0", "latest"],
    "torch": ["==2.5.1", "latest"],
    "torchvision": ["==0.20.1", "latest"],
    "torchaudio": ["==2.5.1", "latest"],
    "opencv-python": ["latest"],
    "faiss-gpu": ["latest"],
    "flask": ["latest"],
    "plyfile": ["latest"],
    "open3d": ["latest"],
    "lightning": ["latest"],
    "deepspeed": ["latest"],
    "einops": ["latest"],
    "gradio": ["latest"],
    "ipykernel": ["latest"],
    "matplotlib": ["latest"],
    "scikit-learn": ["latest"],
    "scikit-video": ["latest"],
    "scikit-image": ["latest"],
    "tqdm": ["latest"],
    "huggingface-hub": ["latest"],
    "hf-transfer": ["latest"],
    "kaggle": ["latest"],
    "accelerate": ["latest"],
    "roma": ["latest"],
    "jaxtyping": ["latest"],
    "lpips": ["latest"],
    "e3nn": ["latest"],
}


def get_package_index_impl(base_url: str, package_name: str) -> list[dict]:
    url = f"{base_url}{package_name}"
    response = requests.get(url)
    response.raise_for_status()
    text = response.text
    soup = BeautifulSoup(text, "html.parser")
    links = soup.find_all("a")
    links_data = [
        {"name": link.text, "url": f"{url}/{link.get('href')}"} for link in links]

    def parse_file_name(file_name: str) -> dict:
        if file_name.endswith(".tar.gz"):
            return {
                "package_name": package_name,
                "package_version": file_name[len(package_name)+1:-7].split("-")[0],
                "python_version": "py3",
                "python_abi": "none",
                "platform": "any",
                "extension": "tar.gz"
            }
        if file_name.endswith(".whl"):
            file_sep = file_name[len(package_name)+1:-4].split("-")
            if len(file_sep) < 4:
                return None
            package_version = file_sep[0]
            python_version = file_sep[1]
            python_abi = file_sep[2]
            platform = file_sep[3]
            return {
                "package_name": package_name,
                "package_version": package_version,
                "python_version": python_version,
                "python_abi": python_abi,
                "platform": platform,
                "extension": "whl"
            }
        return None

    package_data = [
        parse_file_name(link["name"]) for link in links_data
    ]
    package_data = [
        {**link, **package} for link, package in zip(links_data, package_data) if package is not None
    ]

    def get_package_filter_func(package_name: str) -> Callable:
        def filter_func(data: dict) -> bool:
            if "cp3" not in data["python_version"] and "py3" not in data["python_version"]:
                return False
            if "whl" != data["extension"] and "tar.gz" != data["extension"]:
                return False
            if "musllinux" in data["platform"]:
                return False
            if "dev" in data["package_version"]:
                return False
            if "rc" in data["package_version"]:
                return False
            if "post" in data["package_version"]:
                return False
            if "b" in data["package_version"]:
                return False
            if "a" in data["package_version"]:
                return False
            if data["platform"] == "any":
                return True
            if "linux" not in data["platform"]:
                return False
            if "x86_64" not in data["platform"]:
                return False
            return True
        return filter_func
    package_data = list(
        filter(get_package_filter_func(package_name), package_data))
    return package_data


def get_torch_package_index_impl(base_url: str, package_name: str) -> list[dict]:
    url = base_url
    response = requests.get(url)
    response.raise_for_status()
    text = response.text
    soup = BeautifulSoup(text, "html.parser")
    links = soup.find_all("a")
    links_data = [
        {"name": link.text, "url": f"{url}{link.get('href')}"} for link in links]

    links_data = list(
        filter(lambda x: x["name"].startswith(package_name), links_data))

    def parse_file_name(file_name: str) -> dict:
        if file_name.endswith(".tar.gz"):
            return {
                "package_name": package_name,
                "package_version": file_name[len(package_name)+1:-7].split("-")[0],
                "python_version": "py3",
                "python_abi": "none",
                "platform": "any",
                "extension": "tar.gz"
            }
        if file_name.endswith(".whl"):
            file_sep = file_name[len(package_name)+1:-4].split("-")
            if len(file_sep) < 4:
                return None
            package_version = file_sep[0]
            python_version = file_sep[1]
            python_abi = file_sep[2]
            platform = file_sep[3]
            return {
                "package_name": package_name,
                "package_version": package_version,
                "python_version": python_version,
                "python_abi": python_abi,
                "platform": platform,
                "extension": "whl"
            }
        return None
    package_data = [
        parse_file_name(link["name"]) for link in links_data
    ]
    package_data = [
        {**link, **package} for link, package in zip(links_data, package_data) if package is not None
    ]

    def get_package_filter_func(package_name: str) -> Callable:
        def filter_func(data: dict) -> bool:
            if package_name.replace("-", "_") != data["package_name"]:
                return False
            if "musllinux" in data["platform"]:
                return False
            if "linux" not in data["platform"]:
                return False
            if "x86_64" not in data["platform"]:
                return False
            if "whl" != data["extension"]:
                return False
            if "cp3" not in data["python_version"] and "py3" not in data["python_version"]:
                return False
            return True
        return filter_func
    package_data = list(
        filter(get_package_filter_func(package_name), package_data))
    return package_data


def get_package_index(package_name: str) -> list[dict]:
    if "torch" in package_name:
        return get_torch_package_index_impl(TORCH_FIND_LINKS_CU118, package_name) + \
            get_torch_package_index_impl(TORCH_FIND_LINKS_CU126, package_name) + \
            get_torch_package_index_impl(TORCH_FIND_LINKS_CU128, package_name)
    else:
        return get_package_index_impl(INDEX_URL, package_name)


def get_suitable_torch_package_impl(package_data: list[dict],
                                    package_name: str,
                                    python_version: str,
                                    required_packages: dict) -> list[dict]:
    py_version_sep = python_version.split(".")
    py_version_str = f"cp{py_version_sep[0]}{py_version_sep[1]}"

    def filter_python_version(x: dict) -> bool:
        if py_version_str == x["python_version"] and py_version_str == x["python_abi"]:
            return True
        if "py3" == x["python_version"]:
            return True
        if x["python_abi"] == "abi3":
            return True
        if x["python_abi"] == "none":
            return True
        return False
    candidate_package = list(filter(filter_python_version, package_data))
    candidate_wheel = list(
        filter(lambda x: x["extension"] == "whl", candidate_package))

    candidate_wheel_cu118 = list(
        filter(lambda x: "cu118" in x["package_version"], candidate_wheel))
    candidate_wheel_cu126 = list(
        filter(lambda x: "cu126" in x["package_version"], candidate_wheel))
    candidate_wheel_cu128 = list(
        filter(lambda x: "cu128" in x["package_version"], candidate_wheel))

    def match_package_version(x: dict):
        return Version(x["package_version"])

    candidate_wheel_cu118 = sorted(
        candidate_wheel_cu118, key=match_package_version)
    candidate_wheel_cu126 = sorted(
        candidate_wheel_cu126, key=match_package_version)
    candidate_wheel_cu128 = sorted(
        candidate_wheel_cu128, key=match_package_version)

    final_package = []

    required_versions = required_packages[package_name]

    def filter_package_version(req_ver: str):
        optor = ""
        if req_ver[1] == "=":
            optor = req_ver[0:2]
            req_ver = req_ver[2:].strip()
        else:
            optor = req_ver[0]
            req_ver = req_ver[1:].strip()

        def filter_package_version_func(x: dict) -> bool:
            ver_a = Version(x["package_version"].split("+")[0])
            ver_b = Version(req_ver)
            return eval(f"ver_a {optor} ver_b")

        return filter_package_version_func
    for req_ver in required_versions:
        if req_ver == "latest":
            if len(candidate_wheel_cu118) > 0:
                best_wheels = candidate_wheel_cu118[-1]
                final_package.append(best_wheels)
            if len(candidate_wheel_cu126) > 0:
                best_wheels = candidate_wheel_cu126[-1]
                final_package.append(best_wheels)
            if len(candidate_wheel_cu128) > 0:
                best_wheels = candidate_wheel_cu128[-1]
                final_package.append(best_wheels)
            continue

        filtered_wheel_cu118 = list(
            filter(filter_package_version(req_ver), candidate_wheel_cu118))
        filtered_wheel_cu126 = list(
            filter(filter_package_version(req_ver), candidate_wheel_cu126))
        filtered_wheel_cu128 = list(
            filter(filter_package_version(req_ver), candidate_wheel_cu128))
        if len(filtered_wheel_cu118) == 0 and \
            len(filtered_wheel_cu126) == 0 and \
                len(filtered_wheel_cu128) == 0:
            raise ValueError(
                f"No package found for {package_name} {req_ver}")
        if len(filtered_wheel_cu118) > 0:
            final_package.append(filtered_wheel_cu118[-1])
        if len(filtered_wheel_cu126) > 0:
            final_package.append(filtered_wheel_cu126[-1])
        if len(filtered_wheel_cu128) > 0:
            final_package.append(filtered_wheel_cu128[-1])

    return final_package


def get_suitable_package_impl(package_data: list[dict],
                              package_name: str,
                              python_version: str,
                              required_packages: dict) -> list[dict]:
    py_version_sep = python_version.split(".")
    py_version_str = f"cp{py_version_sep[0]}{py_version_sep[1]}"

    def filter_python_version(x: dict) -> bool:
        if py_version_str == x["python_version"] and py_version_str == x["python_abi"]:
            return True
        if "py3" == x["python_version"]:
            return True
        if x["python_abi"] == "abi3":
            return True
        if x["python_abi"] == "none":
            return True
        return False
    candidate_package = list(filter(filter_python_version, package_data))
    candidate_wheel = list(
        filter(lambda x: x["extension"] == "whl", candidate_package))
    candidate_tar_gz = list(
        filter(lambda x: x["extension"] == "tar.gz", candidate_package))

    def match_package_version(x: dict):
        return Version(x["package_version"])

    candidate_wheel = sorted(candidate_wheel, key=match_package_version)
    candidate_tar_gz = sorted(candidate_tar_gz, key=match_package_version)

    final_package = []

    required_versions = required_packages[package_name]

    def filter_package_version(req_ver: str):
        optor = ""
        if req_ver[1] == "=":
            optor = req_ver[0:2]
            req_ver = req_ver[2:].strip()
        else:
            optor = req_ver[0]
            req_ver = req_ver[1:].strip()

        def filter_package_version_func(x: dict) -> bool:
            ver_a = Version(x["package_version"].split("+")[0])
            ver_b = Version(req_ver)
            return eval(f"ver_a {optor} ver_b")

        return filter_package_version_func
    for req_ver in required_versions:
        if req_ver == "latest":
            if len(candidate_wheel) > 0 and len(candidate_tar_gz) > 0:
                best_wheels = candidate_wheel[-1]
                best_tar_gz = candidate_tar_gz[-1]
                if Version(best_wheels["package_version"]) >= Version(best_tar_gz["package_version"]):
                    final_package.append(best_wheels)
                else:
                    final_package.append(best_wheels)
                    final_package.append(best_tar_gz)
            elif len(candidate_wheel) > 0:
                best_wheels = candidate_wheel[-1]
                final_package.append(best_wheels)
            elif len(candidate_tar_gz) > 0:
                best_tar_gz = candidate_tar_gz[-1]
                final_package.append(best_tar_gz)
            continue

        filtered_wheel = list(
            filter(filter_package_version(req_ver), candidate_wheel))
        filtered_tar_gz = list(
            filter(filter_package_version(req_ver), candidate_tar_gz))
        if len(filtered_wheel) == 0 and len(filtered_tar_gz) == 0:
            raise ValueError(f"No package found for {package_name} {req_ver}")
        if len(filtered_wheel) > 0:
            final_package.append(filtered_wheel[-1])
        if len(filtered_tar_gz) > 0:
            final_package.append(filtered_tar_gz[-1])

    return final_package


def get_suitable_package(package_data: list[dict],
                         package_name: str,
                         python_version: str,
                         required_packages: dict) -> list[dict]:
    if "torch" in package_name:
        return get_suitable_torch_package_impl(package_data,
                                               package_name,
                                               python_version,
                                               required_packages)
    else:
        return get_suitable_package_impl(package_data,
                                         package_name,
                                         python_version,
                                         required_packages)


def download_package(data: dict) -> Path:
    wheels_dir = Path("wheels")
    wheels_dir.mkdir(exist_ok=True, parents=True)
    filepath = wheels_dir / str(data["name"])
    if filepath.exists():
        print(f"Already downloaded {data['name']}")
        return filepath

    download_size = 0
    total_size = 0
    Path("./tmp").mkdir(exist_ok=True, parents=True)
    tmp_file = tempfile.NamedTemporaryFile(
        delete_on_close=False, dir="./tmp", buffering=4096, mode="wb")
    for _ in range(3):
        try:
            # 断点续传
            if download_size > 0 and total_size > 0:
                headers = {
                    "Range": f"bytes={download_size}-",
                    "Accept-Encoding": "identity",
                }
            else:
                headers = {
                    "Accept-Encoding": "identity",
                }
            response = requests.get(
                data["url"], stream=True, headers=headers)
            response.raise_for_status()

            # get total file size
            total_size = int(response.headers.get("Content-Length", 0))
            chunk_size = 4096
            print(f"Downloading {data['name']}")
            progress_bar = tqdm(
                total=total_size, unit="B", unit_scale=True)
            progress_bar.update(download_size)
            # temp file to ./tmp/

            for chunk in response.iter_content(chunk_size=chunk_size):
                tmp_file.write(chunk)
                download_size += len(chunk)
                progress_bar.update(len(chunk))
            tmp_file.close()
            shutil.move(tmp_file.name, filepath)
            progress_bar.close()
            return filepath
        except Exception as e:
            print(f"Failed to download {data['name']}")
            progress_bar.close()
    return None


def parse_wheels_dependency(filepath: Path) -> dict:
    pat_1 = re.compile(
        r"""^
        (?P<package_name>[a-zA-Z0-9_\-]+)             # 包名
        (?:
        \s*\(\s*(?P<version_paren>(==|>=|<=|>|<)\s*[^;\)]+)\s*\)
        |
        (?P<version_inline>(==|>=|<=|>|<)\s*[^;\s]+)
        )?
        $""",
        re.VERBOSE
    )
    pat_2 = re.compile(
        r"""^
        (?:extra\s*==\s*["'](?P<extra_name>[^"']+)["'])?
        $""",
        re.VERBOSE
    )
    whl = pkginfo.wheel.Wheel(filepath)
    deps_str = whl.requires_dist
    results = []
    for dep in deps_str:
        dep_sep = list(map(lambda x: x.strip(), dep.split(";")))
        parse_result = {
            "package_name": "",
            "package_version": "",
            "is_extra": False,
        }
        for i, s in enumerate(dep_sep):
            if i == 0:
                match = pat_1.match(s)
                if match:
                    parse_result["package_name"] = match.group(
                        "package_name")
                    parse_result["package_version"] = match.group("version_paren") or \
                        match.group("version_inline") or "latest"
            else:
                match = pat_2.match(s)
                if match:
                    parse_result["is_extra"] = match.group(
                        "extra_name") is not None
        print(f"'{dep}' -> {parse_result}")
        assert parse_result["package_name"] != ""
        assert parse_result["package_version"] != ""
        results.append(parse_result)

    return results


# Example usage
if __name__ == "__main__":
    required_packages = deepcopy(REQUIRED_PACKAGES)
    python_version = PYTHON_VERSIONS[0]
    need_download_package = []
    for package_name in required_packages:
        package_index = get_package_index(package_name)
        suitable_packages = get_suitable_package(
            package_index, package_name, python_version, required_packages)
        need_download_package += suitable_packages

    downloaded_package = []
    for p in need_download_package:
        file_path = download_package(p)
        if file_path is not None:
            downloaded_package.append(file_path)

    # result = parse_wheels_dependency(
    #     Path("wheels\\torch-2.7.1+cu128-cp310-cp310-manylinux_2_28_x86_64.whl"))

    # result = parse_wheels_dependency(
    #     Path("wheels\\torch-2.5.1+cu118-cp310-cp310-linux_x86_64.whl"))

    print("Downloading dependencies...")
    while len(downloaded_package) > 0:
        p = downloaded_package.pop(0)
        result = parse_wheels_dependency(p)
        required_packages = {
            x["package_name"]: [x["package_version"]] for x in result if x["package_name"] != "setuptools"
        }
        need_download_package = []
        for package_name in required_packages:
            package_index = get_package_index(package_name)
            suitable_packages = get_suitable_package(
                package_index, package_name, python_version, required_packages)
            need_download_package += suitable_packages
        for p in need_download_package:
            file_path = download_package(p)
            if file_path is not None:
                downloaded_package.append(file_path)
