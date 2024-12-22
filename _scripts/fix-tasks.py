"""fix tasks."""

# Copyright (c) jupyterlite-pyodide-lock contributors.
# Distributed under the terms of the BSD-3-Clause License.
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import tomli_w
import tomllib

HERE = Path(__file__).parent
ROOT = HERE.parent
PT = ROOT / "pixi.toml"
UTF8 = {"encoding": "utf-8"}
UTF8_NL = {**UTF8, "newline": "\n"}
JSON_FMT: Any = {"indent": 2, "sort_keys": True}


def main() -> int:
    """Update tasks in ``pixi.toml``."""
    ptd = tomllib.loads(PT.read_text(**UTF8))
    old_ptd_json = json.dumps(ptd, **JSON_FMT)

    for epoch in ["oldest", "future"]:
        new_tasks: dict[str, Any]
        for task_name, task in ptd["feature"]["tasks-test"]:
            new_epoch = f"{task_name}-{epoch}"
            new_task = new_tasks[new_epoch] = dict(task)
            new_task.update({
                "description": task["description"].replace("default", epoch),
                "cmd": task["cmd"].replace("-e test", f"-e test-{epoch}"),
            })
            if "depends-on" in task:
                new_task["depends-on"] = [
                    d.replace("-test", f"-test-{epoch}")
                    for d in task.get("depends-on", [])
                ]
            if "inputs" in task:
                new_task["inputs"] = [
                    i.replace("/test/", f"/{new_epoch}/")
                    for i in task.get("inputs", [])
                ]
            if "outputs" in task:
                new_task["outputs"] = [
                    o.replace("/test/", f"/{new_epoch}/")
                    for o in task.get("outputs", [])
                ]

        ptd["feature"][new_epoch] = {"tasks": new_tasks}

    new_ptd_json = json.dumps(ptd, **JSON_FMT)

    if new_ptd_json != old_ptd_json:
        sys.stderr.write("!!! wrote new `pixi.toml`\n")
        PT.write_text(tomli_w.dumps(ptd), **UTF8_NL)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
