from toy_calc import shipping_band

def test_shipping_band_1000_is_standard():
    assert shipping_band(1000) == "standard"

from toy_calc import shipping_band

def test_shipping_band_500_is_standard():
    assert shipping_band(500) == "standard"

from toy_calc import shipping_band

def test_shipping_band_1001_is_heavy():
    assert shipping_band(1001) == "heavy"