"""fix tasks."""

# Copyright (c) jupyterlite-pyodide-lock contributors.
# Distributed under the terms of the BSD-3-Clause License.
from __future__ import annotations

import json
import sys
from difflib import unified_diff
from pathlib import Path
from typing import TYPE_CHECKING, Any

import tomlkit

if TYPE_CHECKING:
    from tomlkit.items import Table

BASE_EPOCH = "test-max"
EPOCHS = ["test-min", "test-next"]

HERE = Path(__file__).parent
ROOT = HERE.parent
PT = ROOT / "pixi.toml"
UTF8 = {"encoding": "utf-8"}
NL = "\n"
UTF8_NL = {**UTF8, "newline": NL}
JSON_FMT: Any = {"indent": 2, "sort_keys": True}


def one_task(
    epoch: str, old_task_name: str, old_task: dict[str, Any]
) -> tuple[str, dict[str, Any]]:
    """Fix a single task."""
    new_task_name = old_task_name.replace(BASE_EPOCH, epoch)
    new_task = dict(old_task)
    new_task.update({
        "description": old_task["description"].replace(
            "default", epoch.replace("test-", "")
        ),
        "cmd": old_task["cmd"].replace(f"-e {BASE_EPOCH}", f"-e {epoch}"),
    })

    if "depends-on" in old_task:
        new_task["depends-on"] = [
            d.replace(f"{BASE_EPOCH}-", f"{epoch}-")
            for d in old_task.get("depends-on", [])
        ]

    for fs in ["inputs", "outputs"]:
        if fs in old_task:
            new_task[fs] = [
                i.replace(f"/{BASE_EPOCH}/", f"/{epoch}/").replace(
                    f"/{BASE_EPOCH}.", f"/{epoch}."
                )
                for i in old_task.get(fs, [])
            ]
    return new_task_name, new_task


def main() -> int:
    """Update tasks in ``pixi.toml``."""
    old_toml = PT.read_text(**UTF8)
    ptd = tomlkit.loads(old_toml)
    old_ptd_json = json.dumps(ptd, **JSON_FMT)
    features: Table | None = ptd.get("feature")
    assert features  # noqa: S101
    base_ft: Table | None = features.get(f"tasks-{BASE_EPOCH}")
    assert base_ft  # noqa: S101

    for epoch in EPOCHS:
        new_feature_name = f"tasks-{epoch}"
        new_tasks = tomlkit.table()
        for task_name, task in base_ft["tasks"].items():
            new_task_name, new_task = one_task(epoch, task_name, task)
            if new_task_name in new_tasks:
                new_tasks[new_task_name] = new_task
            else:
                new_tasks.add(new_task_name, new_task)
        new_feature = tomlkit.table()
        new_feature.add("tasks", new_tasks)
        features.pop(new_feature_name, None)
        features[new_feature_name] = new_feature

    new_ptd_json = json.dumps(ptd, **JSON_FMT)

    if new_ptd_json != old_ptd_json:
        new_toml = tomlkit.dumps(ptd).strip() + NL
        diff = unified_diff(
            new_ptd_json.strip().splitlines(),
            old_ptd_json.strip().splitlines(),
            "OLD",
            "NEW",
        )
        sys.stderr.write(NL.join(diff))
        sys.stderr.write(f"{NL}!!! writing new `pixi.toml`{NL}")
        PT.write_text(new_toml, **UTF8_NL)
        sys.stderr.write(f"{NL}>>> run `pixi run fix`{NL}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
