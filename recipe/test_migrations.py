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

print(f"Checking migrations in {migrations_path}", flush=True)


def test_all_extensions_are_yaml():
    assert set(migrations_path.glob("*.yml")) == set()


@pytest.mark.parametrize("filename", all_migrations)
def test_readable(filename):
    with open(filename, "r", encoding="utf-8") as f:
        yaml.load(f, Loader=yaml.SafeLoader)


@pytest.mark.parametrize("filename", all_migrations)
def test_timestamps_numeric(filename):
    with open(filename, "r", encoding="utf-8") as f:
        data = yaml.load(f, Loader=yaml.SafeLoader)
        assert isinstance(data["migrator_ts"], (int, float)), (
            "Migrator timestamp is not a float or int!"
        )


@pytest.mark.parametrize("filename", all_migrations)
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


def test_uuids_recorded_in_pr():
    with open(
        migrations_path / ".." / "migration_support" / "uuids.yaml",
        "r",
        encoding="utf-8",
    ) as f:
        all_uuids = yaml.load(f, Loader=yaml.SafeLoader)["uuids"]
        assert len(set(all_uuids)) == len(all_uuids)
    all_uuids = frozenset(all_uuids)

    uuids = set()
    for filename in all_migrations:
        with open(filename, "r", encoding="utf-8") as f:
            data = yaml.load(f, Loader=yaml.SafeLoader)
            uuids.add(data["__migrator"]["uuid"])

    assert uuids <= all_uuids, (
        "Some migrator UUIDs are not recorded in the list of all "
        "UUIDs in `recipe/migration_support/uuids.yaml`"
    )


def test_uuids_against_main():
    with open(
        migrations_path / ".." / "migration_support" / "uuids.yaml",
        "r",
        encoding="utf-8",
    ) as f:
        pr_all_uuids = yaml.load(f, Loader=yaml.SafeLoader)["uuids"]
        assert len(set(pr_all_uuids)) == len(pr_all_uuids)
    pr_all_uuids = frozenset(pr_all_uuids)

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
            assert len(set(all_uuids)) == len(all_uuids)
        all_uuids = frozenset(all_uuids)

        curr_migrations = set(
            [
                os.path.basename(pth)
                for pth in glob.glob(
                    os.path.join(tmpdir, "cfp", "recipe", "migrations", "*.yaml")
                )
            ]
        )

    assert len(pr_all_uuids) >= len(all_uuids), (
        "Some UUIDs were removed from `migration_support/uuids.yaml` in the PR. Do not do that!"
    )
    assert all_uuids <= pr_all_uuids, (
        "Some UUIDs were removed from `migration_support/uuids.yaml` in the PR. Do not do that!"
    )

    new_uuids = set()
    old_uuids = set()
    for filename in all_migrations:
        with open(filename, "r", encoding="utf-8") as f:
            data = yaml.load(f, Loader=yaml.SafeLoader)
            if os.path.basename(filename) not in curr_migrations:
                new_uuids.add(data["__migrator"]["uuid"])
            else:
                old_uuids.add(data["__migrator"]["uuid"])

    assert old_uuids <= all_uuids, (
        "Some current migrator UUIDs are not recorded in the list of all "
        "UUIDs in `recipe/migration_support/uuids.yaml` on main!"
    )
    assert new_uuids.isdisjoint(all_uuids), (
        "Some new migrator UUIDs are already recorded in the list of all "
        "UUIDs in `recipe/migration_support/uuids.yaml` on main indicating a UUID collision!"
    )
