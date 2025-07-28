from copy import deepcopy
from functools import reduce
import json
from pathlib import Path
from typing import Callable, Dict, List
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.tags import Tag, parse_tag
from packaging.utils import InvalidWheelFilename, parse_wheel_filename
from packaging.version import InvalidVersion, Version
import requests

INDEX_URL = "https://mirrors.aliyun.com/pypi/simple/"
TORCH_FIND_LINKS_CU118 = "https://mirrors.aliyun.com/pytorch-wheels/cu118/"
TORCH_FIND_LINKS_CU126 = "https://mirrors.aliyun.com/pytorch-wheels/cu126/"
TORCH_FIND_LINKS_CU128 = "https://mirrors.aliyun.com/pytorch-wheels/cu128/"
CACHE_INDEX = {}


def get_parse_file_name_func(pa_name: str) -> Callable:
    def parse_file_name(file_name: str) -> Dict | None:
        if file_name.endswith(".tar.gz"):
            try:
                version = Version(file_name[len(pa_name)+1:-7].split("-")[0])
            except InvalidVersion:
                return None
            return {
                "package_name": pa_name,
                "package_version": version,
                "tags": None,
                "extension": "tar.gz"
            }
        if file_name.endswith(".whl"):
            try:
                _, version, _, tags = parse_wheel_filename(file_name)
                tags = list(tags)
            except InvalidWheelFilename:
                return None
            return {
                "package_name": pa_name,
                "package_version": version,
                "tags": tags,
                "extension": "whl"
            }
        return None
    return parse_file_name


def get_filter_package_func(pa_name: str) -> Callable:
    def filter_package(x):
        name = x["name"]
        if not name.endswith(".whl") and not name.endswith(".tar.gz"):
            return False
        name_sep = name.split("-")
        if len(name_sep) < 1:
            return False
        if name_sep[0].lower().replace("_", "-") != pa_name.lower().replace("_", "-"):
            return False
        return True
    return filter_package


def get_index_by_find_links(pa_name: str, find_links: str) -> List[Dict]:
    url = find_links
    response = requests.get(url)
    response.raise_for_status()
    text = response.text
    soup = BeautifulSoup(text, "html.parser")
    links = soup.find_all("a")
    links_data = [
        {"name": link.text, "url": f"{url}{link.get('href')}"} for link in links]

    links_data = list(filter(get_filter_package_func(pa_name), links_data))

    package_data = [
        get_parse_file_name_func(pa_name)(link["name"]) for link in links_data
    ]
    package_data = [
        {**link, **package} for link, package in zip(links_data, package_data) if package is not None
    ]

    return package_data


def get_index_by_index_url(pa_name: str, index_url: str) -> List[Dict]:
    url = f"{index_url}{pa_name.lower().replace('_', '-')}"
    response = requests.get(url)
    response.raise_for_status()
    text = response.text
    soup = BeautifulSoup(text, "html.parser")
    links = soup.find_all("a")
    links_data = [
        {"name": link.text, "url": f"{url}/{link.get('href')}"} for link in links]

    links_data = list(filter(get_filter_package_func(pa_name), links_data))

    package_data = [
        get_parse_file_name_func(pa_name)(link["name"]) for link in links_data
    ]
    package_data = [
        {**link, **package} for link, package in zip(links_data, package_data) if package is not None
    ]

    return package_data


def get_wheel_index(pa_name: str):
    if pa_name in CACHE_INDEX:
        return CACHE_INDEX[pa_name]

    index_dir = Path("index")

    def decode_index_data(x):
        x = deepcopy(x)
        x["package_version"] = Version(x["package_version"])
        if x["tags"] is not None:
            x["tags"] = list(map(parse_tag, x["tags"]))
            x["tags"] = reduce(lambda x, y: list(x)+list(y), x["tags"])
        else:
            x["tags"] = None
        return x

    index_file = index_dir / f"{pa_name}.json"
    if index_file.exists():
        with index_file.open("r", encoding="utf-8") as f:
            index_json = json.load(f)
        index_data = list(map(decode_index_data, index_json))
        return index_data

    if pa_name in ["torch", "torchvision", "torchaudio"]:
        index_data = get_index_by_find_links(pa_name, TORCH_FIND_LINKS_CU118) + \
            get_index_by_find_links(pa_name, TORCH_FIND_LINKS_CU126) + \
            get_index_by_find_links(pa_name, TORCH_FIND_LINKS_CU128)
    else:
        index_data = get_index_by_index_url(pa_name, INDEX_URL)

    # sort index_data by package_version
    index_data.sort(key=lambda x: x["package_version"])

    def encode_index_data(x):
        x = deepcopy(x)
        x["package_version"] = str(x["package_version"])
        if x["tags"] is not None:
            x["tags"] = list(map(str, x["tags"]))
        return x

    CACHE_INDEX[pa_name] = index_data

    index_dir.mkdir(parents=True, exist_ok=True)
    index_json = list(map(encode_index_data, index_data))
    with index_file.open("w", encoding="utf-8") as f:
        json.dump(index_json, f, indent=4)

    return index_data


def get_suitable_package(pa_name: str,
                         pa_index: List[Dict],
                         pa_ver_spec: SpecifierSet,
                         sys_prof: List[Tag]) -> (List[Dict], List[Dict]):
    def filter_by_tag(x: Dict) -> bool:
        if x["tags"] is None:
            return True
        for tag in x["tags"]:
            if tag in sys_prof:
                return True
        return False

    filt_pa = list(filter(filter_by_tag, pa_index))

    def filter_by_version(x: Dict) -> bool:
        ver = x["package_version"]
        if ver.is_prerelease:
            return False
        if ver.is_devrelease:
            return False
        return pa_ver_spec.contains(ver)

    filt_pa = list(filter(filter_by_version, filt_pa))

    # only consider wheel package
    def filter_by_extrension(x: Dict) -> bool:
        return x["extension"] == "whl"

    filt_pa = list(filter(filter_by_extrension, filt_pa))

    if len(filt_pa) == 0:
        raise ValueError(
            f"No suitable package found for {pa_name} {pa_ver_spec}")
    return filt_pa[-1], filt_pa[0:-1]


if __name__ == "__main__":
    # pa_inex = get_wheel_index("torch")
    # pa_spec = SpecifierSet("==2.5.0")
    # py_ver = "3.10"
    # from wheel_tags import get_compat_wheel_tags, load_linux_x86_64_platforms
    # from packaging.markers import default_environment
    # envs = default_environment()
    # print(json.dumps(envs, indent=4))
    # platforms = load_linux_x86_64_platforms()
    # sys_prof = get_compat_wheel_tags(py_ver, platforms)
    # best_match, candidate = get_suitable_package(
    #     "torch", pa_inex, pa_spec, sys_prof)

    print(get_wheel_index("MarkupSafe"))

    # print(best_match)
    # print(candidate)
