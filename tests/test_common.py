import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from sources.common import infer_prices, category_guess, retailer_from_url


def test_percent_inference():
    current, was, pct = infer_prices("Now $279, was $349, 20% off")
    assert current == 279
    assert was == 349
    assert pct == 20


def test_infer_was_from_percent():
    current, was, pct = infer_prices("$80 20% off")
    assert current == 80
    assert round(was, 2) == 100
    assert pct == 20


def test_categories():
    assert category_guess("Samsung 990 PRO 2TB NVMe SSD") == "Storage"
    assert category_guess("Wi-Fi 7 Router") == "Networking"


def test_retailer():
    assert retailer_from_url("https://www.amazon.com.au/example") == "Amazon AU"
