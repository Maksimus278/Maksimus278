from bot.leads import lead_from_load, parse_contact_parts, unique_leads
from bot.models import Load
from bot.providers.trulos import map_trulos_row


def test_parse_contact_parts():
    company, name, phone = parse_contact_parts(
        "ALLEN LUND COMPANY · Dispatch · 8008895863"
    )
    assert company == "ALLEN LUND COMPANY"
    assert name == "Dispatch"
    assert phone.endswith("8008895863")


def test_unique_leads_from_loads():
    rows = [
        map_trulos_row(
            {
                "LoadID": 1,
                "OriginCity": "CHICAGO",
                "OriginState": "IL",
                "DestinationCity": "DALLAS",
                "DestinationState": "TX",
                "Equipment": "Van",
                "Rate": "2500",
                "Weight": 40000,
                "CompanyName": "ALLEN LUND COMPANY",
                "ContactName": "Dispatch",
                "ContactPhone": "8008895863",
                "PickupDate": "2026-07-24",
            }
        ),
        map_trulos_row(
            {
                "LoadID": 2,
                "OriginCity": "CHICAGO",
                "OriginState": "IL",
                "DestinationCity": "HOUSTON",
                "DestinationState": "TX",
                "Equipment": "Van",
                "Rate": "2200",
                "Weight": 40000,
                "CompanyName": "ALLEN LUND COMPANY",
                "ContactName": "Dispatch",
                "ContactPhone": "8008895863",
                "PickupDate": "2026-07-24",
            }
        ),
        map_trulos_row(
            {
                "LoadID": 3,
                "OriginCity": "CHICAGO",
                "OriginState": "IL",
                "DestinationCity": "MIAMI",
                "DestinationState": "FL",
                "Equipment": "Reefer",
                "Rate": "4300",
                "Weight": 38000,
                "CompanyName": "Sureway Transportation Co",
                "ContactName": "Dispatch",
                "ContactPhone": "8003380497",
                "PickupDate": "2026-07-24",
            }
        ),
    ]
    leads = unique_leads(rows, limit=10)
    assert len(leads) == 2
    assert leads[0].company == "Sureway Transportation Co"
    assert "8003380497" in leads[0].phone
    card = leads[0].format_card(1)
    assert "LEAD #1" in card
    assert "Sureway" in card


def test_lead_requires_phone():
    load = Load(
        id="x",
        origin="Chicago, IL",
        destination="Dallas, TX",
        cargo="Freight",
        weight_lbs=40000,
        contact="Some Broker · Desk",
    )
    assert lead_from_load(load) is None
