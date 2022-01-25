import yaml
from pathlib import Path
import importlib
import sys
from asyd import dictize, build

def import_py_file(path: Path):
    return importlib.import_module(str(path).replace("/", ".")[:-3])

def test():
    scenarios_path = Path("scenarios") # Path(__file__).parent.resolve() / "scenarios"
    for scenario_path in scenarios_path.iterdir():
        if not scenario_path.is_dir() or str(scenario_path).endswith("__pycache__"):
            continue

        print(f"Testing {scenario_path}")

        expected_results_file = scenario_path / "expected_results.py"
        expected_results = import_py_file(expected_results_file).expected_results if expected_results_file.exists() else None

        config_file = scenario_path / "config.py"
        if not config_file.exists():
            raise FileNotFoundError("Config file not found for test scenario.")

        for args, r in expected_results.items():
            print("     Args:", args)
            expected_exception = r["exception"]
            expected_result = r["result"]

            if expected_exception is None and expected_result is None:
                raise Exception("Test scenario must have expected result or expected exception.")

            try:
                cfg = build(import_py_file(config_file).BaseConfig, scenario_path / "config", args=[] if args == "" else args.split(" "))
            except Exception as e:
                assert type(e).__name__ == expected_exception
                raise e

            if not expected_result is None:
                assert expected_result == dictize(cfg)
