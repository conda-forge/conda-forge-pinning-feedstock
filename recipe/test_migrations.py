import datetime
import glob
import os
import subprocess
import tempfile
from pathlib import Path

import pytest
import yaml

PREFIX = os.environ.get("PREFIX", os.environ.get("CONDA_PREFIX"))
if "CONDA_BUILD" in os.environ:
    migrations_path = Path(PREFIX) / "share" / "conda-forge" / "migrations"
else:
    migrations_path = Path(os.path.dirname(__file__)) / "migrations"
all_migrations = list(migrations_path.glob("*.yaml"))
all_migration_ids = [os.path.basename(pth) for pth in all_migrations]

print(f"Checking migrations in {migrations_path}", flush=True)


def _migrator_ts_to_epoch(ts):
    """Return a ``migrator_ts`` as seconds since the Unix epoch.

    A ``migrator_ts`` written as an RFC 3339 date and time is loaded from YAML
    as a datetime, one written as seconds since the epoch as a number.
    """
    if isinstance(ts, datetime.datetime):
        return ts.timestamp()
    return ts


def test_all_extensions_are_yaml():
    assert set(migrations_path.glob("*.yml")) == set()


@pytest.mark.parametrize("filename", all_migrations, ids=all_migration_ids)
def test_readable(filename):
    with open(filename, "r", encoding="utf-8") as f:
        yaml.load(f, Loader=yaml.SafeLoader)


@pytest.mark.parametrize(
    "filename",
    all_migrations + [migrations_path / "example.exyaml"],
    ids=all_migration_ids + ["example.exyaml"],
)
def test_timestamps_numeric_or_rfc3339(filename):
    with open(filename, "r", encoding="utf-8") as f:
        data = yaml.load(f, Loader=yaml.SafeLoader)
        ts = data["migrator_ts"]
        if isinstance(ts, datetime.datetime):
            # would otherwise be read in the local timezone of whoever rerenders
            assert ts.tzinfo is not None, (
                "Migrator timestamp does not include a UTC offset!"
            )
        else:
            assert isinstance(ts, (int, float)), (
                "Migrator timestamp is not a float, an int or an unquoted "
                "RFC 3339 date and time!"
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
            ts = _migrator_ts_to_epoch(data["migrator_ts"])
            assert ts not in timestamps, (
                f"Migrator {os.path.basename(filename)} does not have a unique timestamp!"
            )
            timestamps.add(ts)


def test_timestamps_against_main():
    # we clone here since the main branch on the PR may not be up to date
    # and the tests are run outside of the repo in many cases
    with tempfile.TemporaryDirectory() as tmpdir:
        subprocess.run(
            [
                "git",
                "clone",
                "https://github.com/conda-forge/conda-forge-pinning-feedstock.git",
                os.path.join(tmpdir, "cfp"),
            ],
            check=True,
            capture_output=True,
        )
        if "GIT_REPO_LOC" not in os.environ or not os.environ["GIT_REPO_LOC"]:
            print("Getting new migrations from BASE repo...", flush=True)
            current_migrations = frozenset(
                [
                    os.path.basename(pth)
                    for pth in glob.glob(
                        os.path.join(tmpdir, "cfp", "recipe", "migrations", "*.yaml")
                    )
                ]
            )
            new_files = set()
            for filename in all_migrations:
                if os.path.basename(filename) not in current_migrations:
                    new_files.add(filename)
        else:
            # use main from feedstock checkout in the build
            # so diff of files is accurate even if upstream main is not
            # up to date
            print("Getting new migrations from HEAD repo...", flush=True)
            subprocess.run(
                ["git", "fetch", "--unshallow"],
                cwd=os.environ["GIT_REPO_LOC"],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "fetch", "origin", "main"],
                cwd=os.environ["GIT_REPO_LOC"],
                check=True,
                capture_output=True,
            )
            ret = subprocess.run(
                [
                    "git",
                    "--no-pager",
                    "diff",
                    "--name-only",
                    "--diff-filter=A",
                    "origin/main...HEAD",
                ],
                cwd=os.environ["GIT_REPO_LOC"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
            new_files = set()
            for line in ret.stdout.splitlines():
                line = line.decode("utf-8").strip()
                if (
                    line.startswith("recipe/migrations/")
                    and line.endswith(".yaml")
                    and os.path.basename(line)
                ):
                    new_files.add(
                        os.path.join(
                            migrations_path,
                            os.path.basename(line),
                        )
                    )

        for filename in new_files:
            with open(filename, "r", encoding="utf-8") as f:
                data = yaml.load(f, Loader=yaml.SafeLoader)
                print(
                    f"testing new migration {os.path.basename(filename)}",
                    flush=True,
                )
                ts = data["migrator_ts"]
                if isinstance(ts, datetime.datetime):
                    # as written in the file, up to the seconds
                    ts = ts.strftime("%Y-%m-%dT%H:%M:%S")
                ret = subprocess.run(
                    [
                        "git",
                        "--no-pager",
                        "log",
                        "-S",
                        f"migrator_ts: {ts}",
                    ],
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    cwd=os.path.join(tmpdir, "cfp"),
                )
                assert ret.stdout == b"", (
                    f"Migration {os.path.basename(filename)} doesn't have a unique timestamp! "
                    f"Its timestamp matches commit:\n\n{ret.stdout.decode('utf-8')}"
                )
