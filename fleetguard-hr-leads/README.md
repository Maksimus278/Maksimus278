# FleetGuardAI — Active Trucking HR/Compliance Lead Batch (100k)

**Source:** Public [FMCSA/DOT Company Census File](https://data.transportation.gov/Trucking-and-Motorcoaches/Company-Census-File/az4n-8mr2)

## What this is

~**100,000** active U.S. motor carriers (mid-size+ fleets) with phone on file, exported for B2B outreach to **HR / safety / compliance** buyers.

## Important limitation

FMCSA census lists the **company officer** on the MCS-150 — **not** a verified “HR Manager” title. For fleets this size, that contact is often the owner, safety director, or the person who handles driver onboarding/compliance (the HR-adjacent buyer). Always verify before outreach.

## Filters used

- `status_code = A` (active)
- U.S. physical location
- Phone present
- Fleet size code **D+** (roughly 7+ power units; excludes 1–6 unit micro fleets)
- Prefer / keep rows with **≥4 drivers** or **≥7 power units**

## Files

| File | Rows (approx) |
| --- | --- |
| `fleetguard-hr-leads-part00.csv` | up to 25,000 |
| `fleetguard-hr-leads-part01.csv` | up to 25,000 |
| `fleetguard-hr-leads-part02.csv` | up to 25,000 |
| `fleetguard-hr-leads-part03.csv` | up to 25,000 |

**Total written:** 100,000

## Columns

company, legal_name, usdot, power_units, drivers, primary_contact, phone, email, city, state, safer_url, …

## How to use

1. Import CSVs into your CRM (HubSpot, Salesforce, Sheets).
2. Click `safer_url` to verify the carrier.
3. Ask for **safety / HR / compliance / who handles driver files**.
4. Pitch FleetGuardAI trial: documents + expiration reminders + DOT record view.

## Compliance

Public registration data. Use for legitimate B2B sales. Honor opt-outs. Do **not** blast SMS without prior consent (TCPA).
