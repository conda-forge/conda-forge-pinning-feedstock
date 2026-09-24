import os
import re
import sys
from pathlib import Path


def get_cbc_path():
    # Check PREFIX/conda_build_config.yaml when running in conda-build test env
    prefix = os.environ.get("PREFIX", os.environ.get("CONDA_PREFIX"))
    if prefix:
        p = Path(prefix) / "conda_build_config.yaml"
        if p.is_file():
            return p

    current = Path(__file__).resolve().parent
    candidates = [
        current / "conda_build_config.yaml",
        current.parent / "recipe" / "conda_build_config.yaml",
        current / "recipe" / "conda_build_config.yaml",
    ]
    for c in candidates:
        if c.is_file():
            return c
    raise FileNotFoundError("Could not find recipe/conda_build_config.yaml")


def parse_section(lines, start_idx):
    """Parse key and its list entries until next unindented line or EOF."""
    entries = []
    i = start_idx + 1
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        # Empty line or comment-only line can be within section
        if not stripped or stripped.startswith("#"):
            i += 1
            continue
        # If line is not indented, section has ended
        if not line.startswith(" ") and not line.startswith("\t"):
            break
        entries.append(line)
        i += 1
    return entries, i


def check_stdlib_pinnings(content: str):
    """Validate that required baseline stdlib pinnings are present in conda_build_config.yaml.

    Protects against regressions where migrations accidentally overwrite or remove
    the global Linux/macOS glibc and SDK baselines (e.g., #5559, #7304, #8063, #8853).
    Ref: https://github.com/conda-forge/conda-forge-pinning-feedstock/issues/7307
    """
    errors = []
    lines = content.splitlines()

    c_stdlib_found = False
    m2w64_c_stdlib_found = False

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Check c_stdlib_version
        if re.match(r"^c_stdlib_version\s*:", stripped):
            c_stdlib_found = True
            # Selector must apply to [unix] (must not be constrained to [osx] or similar)
            selector_match = re.search(r"#\s*\[(.*?)\]", line)
            if not selector_match:
                errors.append(
                    f"c_stdlib_version must have a selector comment '# [unix]', but none was found:\n  {line}"
                )
            else:
                selector = selector_match.group(1).strip()
                if "unix" not in selector:
                    errors.append(
                        f"c_stdlib_version must apply to 'unix' (e.g. '# [unix]'), but found '# [{selector}]':\n  {line}"
                    )

            entries, i = parse_section(lines, i)

            # Check required sub-entries:
            # 1. Linux baseline 2.17
            has_linux_217 = False
            for entry in entries:
                if (
                    re.search(r"-\s*['\"]?2\.17['\"]?", entry)
                    and "linux" in entry
                    and "CF_CUDA_ENABLED" not in entry
                ):
                    has_linux_217 = True
                    break
            if not has_linux_217:
                errors.append(
                    "c_stdlib_version is missing general baseline '2.17' for linux (e.g. '- 2.17  # [linux and not riscv64]')."
                )

            # 2. Linux riscv64 baseline 2.39
            has_riscv_239 = False
            for entry in entries:
                if (
                    re.search(r"-\s*['\"]?2\.39['\"]?", entry)
                    and "linux" in entry
                    and "riscv64" in entry
                ):
                    has_riscv_239 = True
                    break
            if not has_riscv_239:
                errors.append(
                    "c_stdlib_version is missing riscv64 baseline '2.39' (e.g. '- 2.39  # [linux and riscv64]')."
                )

            # 3. macOS baseline 11.0
            has_osx_110 = False
            for entry in entries:
                if re.search(r"-\s*['\"]?11\.0['\"]?", entry) and "osx" in entry:
                    has_osx_110 = True
                    break
            if not has_osx_110:
                errors.append(
                    "c_stdlib_version is missing macOS baseline '11.0' (e.g. '- 11.0  # [osx]')."
                )
            continue

        # Check m2w64_c_stdlib_version
        if re.match(r"^m2w64_c_stdlib_version\s*:", stripped):
            m2w64_c_stdlib_found = True
            selector_match = re.search(r"#\s*\[(.*?)\]", line)
            if not selector_match or "win" not in selector_match.group(1):
                errors.append(
                    f"m2w64_c_stdlib_version must have a selector '# [win]', but found:\n  {line}"
                )

            entries, i = parse_section(lines, i)
            has_m2w64_12 = any(
                re.search(r"-\s*['\"]?12['\"]?", entry) and "win" in entry
                for entry in entries
            )
            if not has_m2w64_12:
                errors.append(
                    "m2w64_c_stdlib_version is missing baseline '12' for windows (e.g. '- 12  # [win]')."
                )
            continue

        i += 1

    if not c_stdlib_found:
        errors.append("c_stdlib_version key was not found in conda_build_config.yaml!")

    if not m2w64_c_stdlib_found:
        errors.append(
            "m2w64_c_stdlib_version key was not found in conda_build_config.yaml!"
        )

    return errors


def test_stdlib_pinnings():
    cbc_path = get_cbc_path()
    with open(cbc_path, "r", encoding="utf-8") as f:
        content = f.read()
    errors = check_stdlib_pinnings(content)
    assert not errors, (
        f"Validation failed for stdlib pinnings in {cbc_path}:\n"
        + "\n".join(f"  - {e}" for e in errors)
    )


def main():
    try:
        cbc_path = get_cbc_path()
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    with open(cbc_path, "r", encoding="utf-8") as f:
        content = f.read()

    errors = check_stdlib_pinnings(content)
    if errors:
        print(
            f"ERROR: Baseline stdlib pinnings check failed for {cbc_path}:",
            file=sys.stderr,
        )
        for err in errors:
            print(f"  * {err}", file=sys.stderr)
        print(
            "\nRefer to https://github.com/conda-forge/conda-forge-pinning-feedstock/issues/7307",
            file=sys.stderr,
        )
        return 1

    print(
        f"SUCCESS: Stdlib baseline pinnings in {os.path.basename(cbc_path)} are valid."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
