import glob
import os
from pathlib import Path
import subprocess
import tempfile

import pytest
import yaml

PREFIX = os.environ.get("PREFIX", os.environ.get("CONDA_PREFIX"))
migrations_path = Path(PREFIX) / "share" / "conda-forge" / "migrations"
all_migrations = list(migrations_path.glob("*.yaml"))
all_migration_ids = [os.path.basename(pth) for pth in all_migrations]

print(f"Checking migrations in {migrations_path}", flush=True)


@pytest.fixture(scope="session")
def current_migrations():
    with tempfile.TemporaryDirectory() as tmpdir:
        subprocess.run(
            [
                "git",
                "clone",
                "--depth=1",
                "https://github.com/conda-forge/conda-forge-pinning-feedstock.git",
                os.path.join(tmpdir, "cfp"),
            ],
            check=True,
            capture_output=True,
        )
        return frozenset(
            [
                os.path.basename(pth)
                for pth in glob.glob(
                    os.path.join(tmpdir, "cfp", "recipe", "migrations", "*.yaml")
                )
            ]
        )


def test_all_extensions_are_yaml():
    assert set(migrations_path.glob("*.yml")) == set()


@pytest.mark.parametrize("filename", all_migrations, ids=all_migration_ids)
def test_readable(filename):
    with open(filename, "r", encoding="utf-8") as f:
        yaml.load(f, Loader=yaml.SafeLoader)


@pytest.mark.parametrize("filename", all_migrations, ids=all_migration_ids)
def test_timestamps_numeric(filename):
    with open(filename, "r", encoding="utf-8") as f:
        data = yaml.load(f, Loader=yaml.SafeLoader)
        assert isinstance(data["migrator_ts"], (int, float)), (
            "Migrator timestamp is not a float or int!"
        )


@pytest.mark.parametrize("filename", all_migrations, ids=all_migration_ids)
def test_timestamps_non_none(filename):
    with open(filename, "r", encoding="utf-8") as f:
        data = yaml.load(f, Loader=yaml.SafeLoader)
        assert data["migrator_ts"] not in [None, "None", "none"], (
            f"Migrator {os.path.basename(filename)} does not have a non-None timestamp!"
        )


def test_timestamps_unique_in_pr():
    timestamps = set()
    for filename in all_migrations:
        with open(filename, "r", encoding="utf-8") as f:
            data = yaml.load(f, Loader=yaml.SafeLoader)
            assert data["migrator_ts"] not in timestamps, (
                f"Migrator {os.path.basename(filename)} does not have a unique timestamp!"
            )
            timestamps.add(data["migrator_ts"])


def test_timestamps_against_main():
    # we clone here since the main branch on the PR may not be up to date
    # and the tests are run outside of the repo in many cases
    with tempfile.TemporaryDirectory() as tmpdir:
        subprocess.run(
            [
                "git",
                "clone",
                "--depth=1",
                "https://github.com/conda-forge/conda-forge-pinning-feedstock.git",
                os.path.join(tmpdir, "cfp"),
            ],
            check=True,
            capture_output=True,
        )
        current_migrations = frozenset(
            [
                os.path.basename(pth)
                for pth in glob.glob(
                    os.path.join(tmpdir, "cfp", "recipe", "migrations", "*.yaml")
                )
            ]
        )

        for filename in all_migrations:
            with open(filename, "r", encoding="utf-8") as f:
                data = yaml.load(f, Loader=yaml.SafeLoader)
                if os.path.basename(filename) not in current_migrations:
                    ret = subprocess.run(
                        [
                            "git",
                            "log",
                            "-G",
                            rf"^migrator_ts: +{data['migration_ts']:r}\s*$",
                        ],
                        check=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                    )
                    assert ret.stdout == b"", (
                        f"Migration {os.path.basename(filename)} doesn't have a unique timestamp! "
                        f"It's timestamp matches commit:\n{ret.stdout.decode('utf-8')}"
                    )
