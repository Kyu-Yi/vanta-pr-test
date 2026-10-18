import inflection

def test_pluralize_status_returns_statuses():
    assert inflection.pluralize("status") == "statuses"


def test_pluralize_bus_returns_buses():
    assert inflection.pluralize("bus") == "buses"


def test_pluralize_octopus_returns_octopi():
    assert inflection.pluralize("octopus") == "octopi"
