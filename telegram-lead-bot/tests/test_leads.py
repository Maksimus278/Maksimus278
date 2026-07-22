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
        sample = ROOT / "data" / "fleetguard-leads.sample.csv"
        if not sample.exists():
            raise unittest.SkipTest("sample CSV missing")
        cls.tmp = tempfile.TemporaryDirectory()
        cls.store = LeadStore(sample, Path(cls.tmp.name) / "test.db")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_loads_leads(self):
        self.assertGreater(len(self.store.leads), 100)

    def test_next_best(self):
        leads = self.store.next_best(3)
        self.assertTrue(leads)
        self.assertGreaterEqual(leads[0].effective_score, leads[-1].effective_score)

    def test_status_and_skip_removes_from_next(self):
        lead = self.store.next_best(1)[0]
        self.store.set_status(lead.usdot, "skipped")
        nxt = self.store.next_best(5)
        self.assertTrue(all(x.usdot != lead.usdot for x in nxt))

    def test_follow_up(self):
        lead = self.store.next_best(1)[0]
        self.store.set_status(lead.usdot, "follow_up", follow_up_days=0)
        due = self.store.followups_due()
        self.assertTrue(any(l.usdot == lead.usdot for l, _ in due))

    def test_search(self):
        lead = next(iter(self.store.leads.values()))
        hits = self.store.search(lead.company.split()[0])
        self.assertTrue(hits)

    def test_pitch(self):
        lead = self.store.next_best(1)[0]
        text = personalized_pitch(lead)
        self.assertIn("Call pitch", text)
        self.assertIn(lead.company, format_lead_card(lead))

    def test_stats(self):
        s = self.store.stats()
        self.assertIn("total_leads", s)
        self.assertGreater(s["total_leads"], 0)

    def test_telegram_by_phone(self):
        lead = self.store.next_best(1)[0]
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


if __name__ == "__main__":
    unittest.main()
