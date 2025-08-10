import yaml
from pathlib import Path

import os
PREFIX = os.environ.get('PREFIX', os.environ.get('CONDA_PREFIX'))
migrations_path = Path(PREFIX) / 'share' / 'conda-forge' / 'migrations'

print(f"Checking migrations in {migrations_path}")

for filename in migrations_path.glob('*.yml'):
    raise ValueError(f"Found {filename} with unexpected extension *.yml, please rename to *.yaml")

for filename in migrations_path.glob('*.yaml'):
    print(f"Checking that we can read {filename}")
    with open(filename, 'r', encoding='utf-8') as f:
        data = yaml.load(f, Loader=yaml.SafeLoader)
        assert isinstance(data["migrator_ts"], (int, float))
