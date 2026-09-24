import os
import re
from pathlib import Path


def get_conda_build_config_path() -> Path:
    prefix = os.environ.get("PREFIX", os.environ.get("CONDA_PREFIX"))
    if prefix and (Path(prefix) / "conda_build_config.yaml").is_file():
        return Path(prefix) / "conda_build_config.yaml"
    repo_cbc = Path(__file__).resolve().parent / "conda_build_config.yaml"
    if repo_cbc.is_file():
        return repo_cbc
    return Path("recipe/conda_build_config.yaml")


def test_c_stdlib_version_pinnings():
    cbc_path = get_conda_build_config_path()
    content = cbc_path.read_text(encoding="utf-8")

    match = re.search(
        r"^c_stdlib_version:.*?(?=^cxx_compiler:)",
        content,
        re.MULTILINE | re.DOTALL,
    )
    assert match is not None, (
        f"Could not find 'c_stdlib_version' block before 'cxx_compiler' in {cbc_path}"
    )

    section = match.group(0)
    lines = section.splitlines()

    # unix selector on c_stdlib_version header
    assert any(re.search(r"c_stdlib_version:\s+#\s*\[unix\]", x) for x in lines), (
        "c_stdlib_version selector must be '[unix]'"
    )
    # linux default
    assert any(re.search(r"2\.17\s+#\s*\[linux and not riscv64\]", x) for x in lines), (
        "Could not find expected glibc pin: 2.17 # [linux and not riscv64]"
    )
    # linux-riscv64 started off with glibc 2.39
    assert any(re.search(r"2\.39\s+#\s*\[linux and riscv64\]", x) for x in lines), (
        "Could not find expected glibc pin: 2.39 # [linux and riscv64]"
    )
    # linux & CUDA 12.9
    assert any(re.search(r"2\.17\s+#\s*\[linux.*CF_CUDA_ENABLED", x) for x in lines), (
        "Could not find expected glibc pin for CUDA 12.x builds: 2.17"
    )
    # linux & CUDA 13.x
    assert any(re.search(r"2\.28\s+#\s*\[linux.*CF_CUDA_ENABLED", x) for x in lines), (
        "Could not find expected glibc pin for CUDA 13.x builds: 2.28"
    )
    # osx
    assert any(re.search(r"11\.0\s+#\s*\[osx\]", x) for x in lines), (
        "Could not find expected macosx_deployment_target pin: 11.0 # [osx]"
    )


if __name__ == "__main__":
    test_c_stdlib_version_pinnings()
    print("All stdlib pinning checks passed.")
