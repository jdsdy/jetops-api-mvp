from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_PLANS_DIR = PROJECT_ROOT / "ExampleFlightPlans"
FLIGHT_DATA_FIXTURES = PROJECT_ROOT / "tests" / "fixtures" / "flight_data_expected.json"
NOTAM_FIXTURES = PROJECT_ROOT / "tests" / "fixtures" / "notam_expected.json"
