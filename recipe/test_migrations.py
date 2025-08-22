import os
from pathlib import Path

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


def test_uuids_unique_and_recorded():
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
            assert data["__migrator"].get("uuid", None) is not None, (
                f"Migrator {os.path.basename(filename)} does not have a non-None UUID!"
            )
            assert data["__migrator"]["uuid"] not in uuids, (
                f"Migrator {os.path.basename(filename)} does not have a unique UUID!"
            )
            uuids.add(data["__migrator"]["uuid"])

    assert uuids <= all_uuids, (
        "Some migrator UUIDs are not recorded in the list of all "
        "UUIDs in `recipe/migration_support/uuids.yaml`"
    )
