from typing import Dict, List, Optional


def get_python_environment(python_version: str) -> Dict[str, str]:
    # from packaging.markers import default_environment
    envs = {
        "implementation_name": "cpython",
        "os_name": "posix",
        "platform_machine": "x86_64",
        "platform_release": "5.15.0-139-generic",
        "platform_system": "Linux",
        "platform_version": "#149~20.04.1-Ubuntu SMP Wed Apr 16 08:29:56 UTC 2025",
        "platform_python_implementation": "CPython",
        "sys_platform": "linux"
    }
    if python_version == "3.10":
        envs["implementation_version"] = "3.10.18"
        envs["python_full_version"] = "3.10.18"
        envs["python_version"] = "3.10"
    if python_version == "3.11":
        envs["implementation_version"] = "3.11.13"
        envs["python_full_version"] = "3.11.13"
        envs["python_version"] = "3.11"
    if python_version == "3.12":
        envs["implementation_version"] = "3.12.11"
        envs["python_full_version"] = "3.12.11"
        envs["python_version"] = "3.12"
    if python_version == "3.13":
        envs["implementation_version"] = "3.13.5"
        envs["python_full_version"] = "3.13.5"
        envs["python_version"] = "3.13"
    return envs


if __name__ == "__main__":
    print(get_python_environment("3.10"))
    print(get_python_environment("3.11"))
    print(get_python_environment("3.12"))
    print(get_python_environment("3.13"))
