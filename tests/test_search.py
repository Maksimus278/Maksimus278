from bot.models import SearchQuery
from bot.search import LoadRepository, normalize_city, parse_route_text


def test_normalize_city_aliases():
    assert normalize_city("МСК") == "москва"
    assert normalize_city("Питер") == "санкт-петербург"
    assert normalize_city("Екб") == "екатеринбург"


def test_parse_route_text():
    q = parse_route_text("Москва -> СПб")
    assert q.origin == "москва"
    assert q.destination == "санкт-петербург"

    q2 = parse_route_text("Казань")
    assert q2.origin == "казань"
    assert q2.destination is None


def test_search_loads(tmp_path):
    data = tmp_path / "loads.json"
    data.write_text(
        """
        [
          {
            "id": "1",
            "origin": "Москва",
            "destination": "Казань",
            "cargo": "ТНП",
            "weight_tons": 10,
            "truck_type": "тент",
            "rate": 40000
          },
          {
            "id": "2",
            "origin": "Москва",
            "destination": "Санкт-Петербург",
            "cargo": "Продукты",
            "weight_tons": 18,
            "truck_type": "рефрижератор",
            "rate": 50000
          }
        ]
        """,
        encoding="utf-8",
    )
    repo = LoadRepository(data)
    found = repo.search(SearchQuery(origin="мск", destination="казань"))
    assert len(found) == 1
    assert found[0].id == "1"

    refrigerators = repo.search(SearchQuery(origin="москва", truck_type="рефрижератор"))
    assert len(refrigerators) == 1
    assert refrigerators[0].id == "2"
