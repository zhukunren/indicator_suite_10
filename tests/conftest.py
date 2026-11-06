"""Keep generated test data inside this project, avoiding shared Temp ACLs."""
from pathlib import Path
from uuid import uuid4


def pytest_configure(config):
    if not config.option.basetemp:
        root=Path(__file__).resolve().parents[1]/'.runtime'/'tests'
        root.mkdir(parents=True,exist_ok=True)
        config.option.basetemp=str(root/uuid4().hex)
