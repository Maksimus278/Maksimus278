from bot.models import SearchQuery
from bot.providers.trulos import map_trulos_row
from bot.search import LoadRepository, normalize_city, parse_route_text


def test_normalize_us_city_aliases():
    assert normalize_city("LA") == "los angeles, ca"
    assert normalize_city("Chicago") == "chicago, il"
    assert normalize_city("DFW") == "dallas, tx"
    assert normalize_city("NYC") == "new york, ny"


def test_parse_route_text_us():
    q = parse_route_text("Chicago -> Dallas")
    assert q.origin == "chicago, il"
    assert q.destination == "dallas, tx"

    q2 = parse_route_text("LA to Phoenix")
    assert q2.origin == "los angeles, ca"
    assert q2.destination == "phoenix, az"

    q3 = parse_route_text("Atlanta")
    assert q3.origin == "atlanta, ga"
    assert q3.destination is None


def test_search_us_loads(tmp_path):
    data = tmp_path / "loads.json"
    data.write_text(
        """
        [
          {
            "id": "1",
            "origin": "Chicago, IL",
            "destination": "Dallas, TX",
            "cargo": "Pallets",
            "weight_lbs": 40000,
            "truck_type": "dry van",
            "rate": 2800
          },
          {
            "id": "2",
            "origin": "Los Angeles, CA",
            "destination": "Phoenix, AZ",
            "cargo": "Produce",
            "weight_lbs": 38000,
            "truck_type": "reefer",
            "rate": 1450
          },
          {
            "id": "3",
            "origin": "Dallas, TX",
            "destination": "New York, NY",
            "cargo": "Retail",
            "weight_lbs": 36000,
            "truck_type": "dry van",
            "rate": 4000
          }
        ]
        """,
        encoding="utf-8",
    )
    repo = LoadRepository(data)
    found = repo.search(SearchQuery(origin="chi", destination="dallas"))
    assert len(found) == 1
    assert found[0].id == "1"

    reefers = repo.search(SearchQuery(origin="la", truck_type="reefer"))
    assert len(reefers) == 1
    assert reefers[0].id == "2"

    nyc = repo.search(SearchQuery(origin="nyc"))
    assert [x.id for x in nyc] == ["3"]


def test_map_trulos_row_real_shape():
    load = map_trulos_row(
        {
            "LoadID": 21456690,
            "PickupDate": "2026-07-24",
            "OriginCity": "CHICAGO",
            "OriginState": "IL",
            "DestinationCity": "SPRINGFIELD",
            "DestinationState": "MO",
            "Equipment": "Flatbed/Step Deck",
            "Rate": "1650",
            "Weight": 48000,
            "loadSize": "Full",
            "ContactName": "Dispatch Omaha",
            "ContactPhone": "4029911641",
            "CompanyName": "KLC Logistics, INC",
            "Comment": "tarps",
            "DistanceMiles": 450,
        }
    )
    assert load.id == "TR-21456690"
    assert load.origin == "Chicago, IL"
    assert load.destination == "Springfield, MO"
    assert load.rate == 1650
    assert load.rate_per_mile == 3.67
    assert load.source == "Trulos (live)"
    assert "4029911641" in load.contact
