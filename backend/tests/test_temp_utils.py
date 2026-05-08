from __future__ import annotations

import gc
import shutil
import sqlite3
import time
from pathlib import Path
from uuid import uuid4

BACKEND_ROOT = Path(__file__).resolve().parents[1]
TEST_TMP_ROOT = BACKEND_ROOT / "_tmp_test"


def make_test_dir(prefix: str) -> Path:
    path = TEST_TMP_ROOT / f"{prefix}_{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def connect_test_sqlite(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def cleanup_test_dir(path: Path) -> None:
    root = TEST_TMP_ROOT.resolve()
    target = path.resolve()
    if root != target and root not in target.parents:
        raise ValueError(f"refuse_to_cleanup_outside_test_tmp: {target}")
    for _ in range(5):
        try:
            shutil.rmtree(target, ignore_errors=False)
            return
        except FileNotFoundError:
            return
        except PermissionError:
            gc.collect()
            time.sleep(0.1)
    shutil.rmtree(target, ignore_errors=True)
