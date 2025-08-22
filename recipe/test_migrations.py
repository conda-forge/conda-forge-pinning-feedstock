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
def pr_all_uuids():
    with open(
        migrations_path / ".." / "migration_support" / "uuids.yaml",
        "r",
        encoding="utf-8",
    ) as f:
        all_uuids = frozenset(yaml.load(f, Loader=yaml.SafeLoader)["uuids"])
    return all_uuids


@pytest.fixture(scope="session")
def main_all_uuids():
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
            os.path.join(tmpdir, "cfp", "recipe", "migration_support", "uuids.yaml"),
            "r",
            encoding="utf-8",
        ) as f:
            all_uuids = yaml.load(f, Loader=yaml.SafeLoader)["uuids"]
            assert len(set(all_uuids)) == len(all_uuids), (
                "UUIDs in `recipe/migration_support/uuids.yaml` on main are not unique!"
            )
        return frozenset(all_uuids)


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


def test_pr_all_uuids_unique():
    with open(
        migrations_path / ".." / "migration_support" / "uuids.yaml",
        "r",
        encoding="utf-8",
    ) as f:
        all_uuids = yaml.load(f, Loader=yaml.SafeLoader)["uuids"]
        assert len(set(all_uuids)) == len(all_uuids), (
            "UUIDs in `recipe/migration_support/uuids.yaml` in pr are not unique!"
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
def test_uuids_non_none(filename):
    with open(filename, "r", encoding="utf-8") as f:
        data = yaml.load(f, Loader=yaml.SafeLoader)
        assert data["__migrator"].get("uuid", None) not in [None, "None", "none"], (
            f"Migrator {os.path.basename(filename)} does not have a non-None UUID!"
        )


def test_uuids_unique_in_pr():
    uuids = set()
    for filename in all_migrations:
        with open(filename, "r", encoding="utf-8") as f:
            data = yaml.load(f, Loader=yaml.SafeLoader)
            assert data["__migrator"]["uuid"] not in uuids, (
                f"Migrator {os.path.basename(filename)} does not have a unique UUID!"
            )
            uuids.add(data["__migrator"]["uuid"])


@pytest.mark.parametrize("filename", all_migrations, ids=all_migration_ids)
def test_uuids_recorded_in_pr(filename, pr_all_uuids):
    with open(filename, "r", encoding="utf-8") as f:
        data = yaml.load(f, Loader=yaml.SafeLoader)
        assert data["__migrator"]["uuid"] in pr_all_uuids, (
            f"Migrator {os.path.basename(filename)} does not have its "
            "UUID recorded in `recipe/migration_support/uuids.yaml`!"
        )


def test_uuids_against_main(pr_all_uuids, main_all_uuids, current_migrations):
    assert len(pr_all_uuids) >= len(main_all_uuids), (
        "Some UUIDs were removed from `migration_support/uuids.yaml` in the PR. Do not do that!"
    )
    assert main_all_uuids <= pr_all_uuids, (
        "Some UUIDs were removed from `migration_support/uuids.yaml` in the PR. Do not do that!"
    )

    new_uuids = set()
    old_uuids = set()
    for filename in all_migrations:
        with open(filename, "r", encoding="utf-8") as f:
            data = yaml.load(f, Loader=yaml.SafeLoader)
            if os.path.basename(filename) not in current_migrations:
                new_uuids.add(data["__migrator"]["uuid"])
            else:
                old_uuids.add(data["__migrator"]["uuid"])

    assert old_uuids <= main_all_uuids, (
        "Some current migrator UUIDs are not recorded in the list of all "
        "UUIDs in `recipe/migration_support/uuids.yaml` on main!"
    )
    assert new_uuids.isdisjoint(main_all_uuids), (
        "Some new migrator UUIDs are already recorded in the list of all "
        "UUIDs in `recipe/migration_support/uuids.yaml` on main indicating a UUID collision!"
    )
