from pathlib import Path
import shutil

from requests import Session
from requests.adapters import HTTPAdapter
from tqdm import tqdm
from urllib3.util.retry import Retry


def _make_session() -> Session:
    s = Session()
    retry = Retry(
        total=5,
        backoff_factor=0.5,
        status_forcelist=(500, 502, 503, 504),
        allowed_methods=["GET"],
    )
    s.mount("https://", HTTPAdapter(max_retries=retry))
    return s


SESSION = _make_session()


def download_package(data: dict) -> Path:
    wheels_dir = Path("wheels")
    wheels_dir.mkdir(exist_ok=True, parents=True)
    pkg_name: str = data["name"]
    filepath = wheels_dir / pkg_name
    if filepath.exists():
        print(f"Already downloaded {pkg_name}")
        return filepath

    download_size = 0
    total_size = 0
    tmp_dir = Path("./tmp")
    tmp_dir.mkdir(exist_ok=True, parents=True)
    tmp_file = tmp_dir / pkg_name
    if tmp_file.exists():
        download_size = tmp_file.stat().st_size

    pbar = None
    try:
        # 断点续传
        if download_size > 0:
            headers = {
                "Range": f"bytes={download_size}-",
                "Accept-Encoding": "identity",
            }
        else:
            headers = {
                "Accept-Encoding": "identity",
            }

        with SESSION.get(data["url"], stream=True, headers=headers) as resp:
            resp.raise_for_status()
            # print(f"Content-Range: {resp.headers.get('Content-Range')}")
            # print(f"Content-Length: {resp.headers.get('Content-Length')}")

            if "Content-Range" in resp.headers:
                total_size = int(resp.headers.get(
                    "Content-Range", "bytes */0").split("/")[-1])
            else:
                total_size = int(resp.headers.get("Content-Length", 0))

            chunk_size = 4096
            print(f"Downloading {data['name']}")
            pbar = tqdm(
                total=total_size, unit="B", unit_scale=True)
            pbar.update(download_size)

            with open(tmp_file, "ab") as f:
                for chunk in resp.iter_content(chunk_size=chunk_size):
                    f.write(chunk)
                    download_size += len(chunk)
                    pbar.update(len(chunk))
            pbar.close()
            shutil.move(tmp_file, filepath)
            return filepath
    except Exception as e:
        print(f"Failed to download {data['name']}")
        if pbar:
            pbar.close()
    return None


if __name__ == "__main__":
    print(download_package({
        "name": "testa.whl",
        "url": "https://mirrors.aliyun.com/pytorch-wheels/cu118/torch-2.7.1+cu118-cp310-cp310-manylinux_2_28_x86_64.whl"
    }))
