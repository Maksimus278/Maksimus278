#!/usr/bin/env python3
"""Smoke tests that do not need a Telegram token."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bot.leads import LeadStore  # noqa: E402
from bot.pitches import format_lead_card, personalized_pitch  # noqa: E402


class LeadBotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Prefer full CSV so ~300-truck fleets exist; fall back to sample
        full = ROOT / "data" / "fleetguard-leads.csv"
        sample = ROOT / "data" / "fleetguard-leads.sample.csv"
        csv_path = full if full.exists() else sample
        if not csv_path.exists():
            raise unittest.SkipTest("CSV missing")
        cls.tmp = tempfile.TemporaryDirectory()
        cls.store = LeadStore(csv_path, Path(cls.tmp.name) / "test.db")
        cls.using_full = csv_path == full

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_loads_leads(self):
        self.assertGreater(len(self.store.leads), 100)

    def test_next_best_prefers_near_300_trucks(self):
        leads = self.store.next_best(5, target_trucks=300, truck_min=200, truck_max=450)
        self.assertTrue(leads)
        if self.using_full:
            for lead in leads:
                self.assertTrue(200 <= lead.power_units <= 450)
            # Closest to 300 first
            distances = [lead.truck_distance(300) for lead in leads]
            self.assertEqual(distances, sorted(distances))

    def test_status_and_skip_removes_from_next(self):
        lead = self.store.next_best(1, target_trucks=300, truck_min=200, truck_max=450)[0]
        self.store.set_status(lead.usdot, "skipped")
        nxt = self.store.next_best(5, target_trucks=300, truck_min=200, truck_max=450)
        self.assertTrue(all(x.usdot != lead.usdot for x in nxt))

    def test_follow_up(self):
        lead = self.store.next_best(1, target_trucks=300, truck_min=200, truck_max=450)[0]
        self.store.set_status(lead.usdot, "follow_up", follow_up_days=0)
        due = self.store.followups_due()
        self.assertTrue(any(l.usdot == lead.usdot for l, _ in due))

    def test_search(self):
        lead = next(iter(self.store.leads.values()))
        hits = self.store.search(lead.company.split()[0])
        self.assertTrue(hits)

    def test_pitch(self):
        lead = self.store.next_best(1, target_trucks=300, truck_min=200, truck_max=450)[0]
        text = personalized_pitch(lead, sender_name="Alex Rivera", sender_phone="555-0100")
        self.assertIn("CALL", text)
        self.assertIn("Alex Rivera", text)
        self.assertIn("555-0100", text)
        self.assertIn("EMAIL BODY", text)
        self.assertIn("fleetguardlogistics.com", text.lower())
        from bot.pitches import copy_text_version, sms_text
        sms = copy_text_version(lead, sender_name="Alex Rivera")
        self.assertEqual(sms, sms_text(lead, sender_name="Alex Rivera"))
        self.assertIn("Alex Rivera", sms)
        self.assertNotIn("EMAIL BODY", sms)
        self.assertNotIn("CALL\n", sms)
        card = format_lead_card(lead)
        self.assertIn("Trucks:", card)
        self.assertNotIn("<b>", card)

    def test_sender_name_profile(self):
        self.store.set_sender_name(42, "Sam Fleet")
        self.store.set_sender_phone(42, "5559998888")
        name, phone = self.store.resolve_sender(42, "Fallback")
        self.assertEqual(name, "Sam Fleet")
        self.assertEqual(phone, "5559998888")
        text = personalized_pitch(
            self.store.next_best(1, target_trucks=300, truck_min=200, truck_max=450)[0],
            sender_name=name,
            sender_phone=phone,
        )
        self.assertIn("Sam Fleet", text)

    def test_stats(self):
        s = self.store.stats()
        self.assertIn("total_leads", s)
        self.assertGreater(s["total_leads"], 0)

    def test_telegram_by_phone(self):
        lead = self.store.next_best(1, target_trucks=300, truck_min=200, truck_max=450)[0]
        self.assertTrue(lead.phone)
        self.store.set_telegram_for_phone(
            lead.phone,
            telegram_user_id=999001,
            telegram_username="fleetowner",
            usdot=lead.usdot,
        )
        row = self.store.get_telegram_by_phone(lead.phone)
        self.assertIsNotNone(row)
        self.assertEqual(row["telegram_user_id"], 999001)
        self.assertEqual(row["telegram_username"], "fleetowner")
        by_lead = self.store.get_telegram_for_lead(lead.usdot)
        self.assertEqual(by_lead["telegram_username"], "fleetowner")

    def test_highscore_near_300_trucks(self):
        rows = self.store.high_score(5, target_trucks=300, truck_min=200, truck_max=450)
        self.assertTrue(rows)
        if self.using_full:
            for lead, _ in rows:
                self.assertTrue(200 <= lead.power_units <= 450)
            # First should be very close to 300
            self.assertLessEqual(rows[0][0].truck_distance(300), 50)


if __name__ == "__main__":
    unittest.main()
