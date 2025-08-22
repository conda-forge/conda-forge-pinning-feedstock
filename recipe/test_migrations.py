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
def pr_all_timestamps():
    with open(
        migrations_path / ".." / "migration_support" / "timestamps.yaml",
        "r",
        encoding="utf-8",
    ) as f:
        all_timestamps = frozenset(yaml.load(f, Loader=yaml.SafeLoader)["timestamps"])
    return all_timestamps


@pytest.fixture(scope="session")
def main_all_timestamps():
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
        with open(
            os.path.join(
                tmpdir, "cfp", "recipe", "migration_support", "timestamps.yaml"
            ),
            "r",
            encoding="utf-8",
        ) as f:
            all_timestamps = yaml.load(f, Loader=yaml.SafeLoader)["timestamps"]
            assert len(set(all_timestamps)) == len(all_timestamps), (
                "timestamps in `recipe/migration_support/timestamps.yaml` on main are not unique!"
            )
        return frozenset(all_timestamps)


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


def test_pr_all_timestamps_unique():
    with open(
        migrations_path / ".." / "migration_support" / "timestamps.yaml",
        "r",
        encoding="utf-8",
    ) as f:
        all_timestamps = yaml.load(f, Loader=yaml.SafeLoader)["timestamps"]
        assert len(set(all_timestamps)) == len(all_timestamps), (
            "timestamps in `recipe/migration_support/timestamps.yaml` in pr are not unique!"
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
            print("  - " + data["migrator_ts"], flush=True)


@pytest.mark.parametrize("filename", all_migrations, ids=all_migration_ids)
def test_timestamps_recorded_in_pr(filename, pr_all_timestamps):
    with open(filename, "r", encoding="utf-8") as f:
        data = yaml.load(f, Loader=yaml.SafeLoader)
        assert data["migrator_ts"] in pr_all_timestamps, (
            f"Migrator {os.path.basename(filename)} does not have its "
            "timestamp recorded in `recipe/migration_support/timestamps.yaml`!"
        )


def test_timestamps_against_main(
    pr_all_timestamps, main_all_timestamps, current_migrations
):
    assert len(pr_all_timestamps) >= len(main_all_timestamps), (
        "Some timestamps were removed from `migration_support/timestamps.yaml` in the PR. Do not do that!"
    )
    assert main_all_timestamps <= pr_all_timestamps, (
        "Some timestamps were removed from `migration_support/timestamps.yaml` in the PR. Do not do that!"
    )

    new_timestamps = set()
    old_timestamps = set()
    for filename in all_migrations:
        with open(filename, "r", encoding="utf-8") as f:
            data = yaml.load(f, Loader=yaml.SafeLoader)
            if os.path.basename(filename) not in current_migrations:
                new_timestamps.add(data["migrator_ts"])
            else:
                old_timestamps.add(data["migrator_ts"])

    assert old_timestamps <= main_all_timestamps, (
        "Some current migrator timestamps are not recorded in the list of all "
        "timestamps in `recipe/migration_support/timestamps.yaml` on main!"
    )
    assert new_timestamps.isdisjoint(main_all_timestamps), (
        "Some new migrator timestamps are already recorded in the list of all "
        "timestamps in `recipe/migration_support/timestamps.yaml` on main indicating a timestamp collision!"
    )
