from __future__ import annotations

import csv
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

from .phones import normalize_phone, phone_match_keys, phones_equal


STATUSES = (
    "new",
    "skipped",
    "contacted",
    "interested",
    "follow_up",
    "closed_won",
    "closed_lost",
)


@dataclass(frozen=True)
class Lead:
    usdot: str
    fit_tier: str
    priority: str
    company: str
    legal_name: str
    power_units: int
    drivers: int
    officer: str
    phone: str
    email: str
    city: str
    state: str
    zip: str
    address: str
    safety_rating: str
    hazmat: str
    classdef: str
    fit_score: int
    suggested_plan: str
    add_on: str
    outreach_angle: str
    safer_url: str

    @property
    def effective_score(self) -> int:
        score = self.fit_score
        if self.priority.lower() == "high":
            score += 15
        if self.email:
            score += 8
        if self.phone:
            score += 5
        if self.fit_tier == "Growth":
            score += 4
        elif self.fit_tier == "Fleet":
            score += 6
        return score


def _to_int(value: str | None, default: int = 0) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return default


def load_leads_from_csv(path: Path) -> dict[str, Lead]:
    if not path.exists():
        raise FileNotFoundError(f"Leads CSV not found: {path}")

    leads: dict[str, Lead] = {}
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        required = {"usdot", "company", "fit_score"}
        if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
            raise ValueError(
                f"CSV missing required columns. Found: {reader.fieldnames}"
            )
        for row in reader:
            usdot = (row.get("usdot") or "").strip()
            if not usdot or usdot in leads:
                continue
            leads[usdot] = Lead(
                usdot=usdot,
                fit_tier=(row.get("fit_tier") or "").strip(),
                priority=(row.get("priority") or "").strip(),
                company=(row.get("company") or row.get("legal_name") or "").strip(),
                legal_name=(row.get("legal_name") or "").strip(),
                power_units=_to_int(row.get("power_units")),
                drivers=_to_int(row.get("drivers")),
                officer=(row.get("officer") or "").strip(),
                phone=(row.get("phone") or "").strip(),
                email=(row.get("email") or "").strip(),
                city=(row.get("city") or "").strip(),
                state=(row.get("state") or "").strip(),
                zip=(row.get("zip") or "").strip(),
                address=(row.get("address") or "").strip(),
                safety_rating=(row.get("safety_rating") or "").strip(),
                hazmat=(row.get("hazmat") or "").strip(),
                classdef=(row.get("classdef") or "").strip(),
                fit_score=_to_int(row.get("fit_score")),
                suggested_plan=(row.get("suggested_plan") or "").strip(),
                add_on=(row.get("add_on") or "").strip(),
                outreach_angle=(row.get("outreach_angle") or "").strip(),
                safer_url=(row.get("safer_url") or "").strip(),
            )
    return leads


class LeadStore:
    """CSV leads + SQLite outreach state."""

    def __init__(self, csv_path: Path, db_path: Path):
        self.csv_path = csv_path
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.leads = load_leads_from_csv(csv_path)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS lead_state (
                    usdot TEXT PRIMARY KEY,
                    status TEXT NOT NULL DEFAULT 'new',
                    notes TEXT NOT NULL DEFAULT '',
                    follow_up_at TEXT,
                    last_contacted_at TEXT,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    usdot TEXT NOT NULL,
                    action TEXT NOT NULL,
                    detail TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS telegram_by_phone (
                    phone_norm TEXT PRIMARY KEY,
                    telegram_user_id INTEGER,
                    telegram_username TEXT NOT NULL DEFAULT '',
                    display_phone TEXT NOT NULL DEFAULT '',
                    usdot TEXT NOT NULL DEFAULT '',
                    source TEXT NOT NULL DEFAULT 'manual',
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_tg_usdot
                ON telegram_by_phone(usdot)
                """
            )
            conn.commit()

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def get_lead(self, usdot: str) -> Lead | None:
        return self.leads.get(usdot)

    def get_status(self, usdot: str) -> sqlite3.Row | None:
        with self._connect() as conn:
            return conn.execute(
                "SELECT * FROM lead_state WHERE usdot = ?", (usdot,)
            ).fetchone()

    def _log(self, conn: sqlite3.Connection, usdot: str, action: str, detail: str = "") -> None:
        conn.execute(
            "INSERT INTO events (usdot, action, detail, created_at) VALUES (?, ?, ?, ?)",
            (usdot, action, detail, self._now()),
        )

    def set_status(
        self,
        usdot: str,
        status: str,
        *,
        notes: str | None = None,
        follow_up_days: int | None = None,
        clear_follow_up: bool = False,
    ) -> None:
        if status not in STATUSES:
            raise ValueError(f"Unknown status: {status}")
        now = self._now()
        follow_up_at = None
        if follow_up_days is not None:
            follow_up_at = (
                datetime.now(timezone.utc) + timedelta(days=follow_up_days)
            ).isoformat()
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT notes FROM lead_state WHERE usdot = ?", (usdot,)
            ).fetchone()
            merged_notes = notes if notes is not None else (existing["notes"] if existing else "")
            if existing:
                if clear_follow_up:
                    conn.execute(
                        """
                        UPDATE lead_state
                        SET status = ?, notes = ?, follow_up_at = NULL,
                            last_contacted_at = CASE
                                WHEN ? IN ('contacted','interested','follow_up') THEN ?
                                ELSE last_contacted_at
                            END,
                            updated_at = ?
                        WHERE usdot = ?
                        """,
                        (status, merged_notes, status, now, now, usdot),
                    )
                elif follow_up_at:
                    conn.execute(
                        """
                        UPDATE lead_state
                        SET status = ?, notes = ?, follow_up_at = ?,
                            last_contacted_at = ?, updated_at = ?
                        WHERE usdot = ?
                        """,
                        (status, merged_notes, follow_up_at, now, now, usdot),
                    )
                else:
                    conn.execute(
                        """
                        UPDATE lead_state
                        SET status = ?, notes = ?,
                            last_contacted_at = CASE
                                WHEN ? IN ('contacted','interested','follow_up') THEN ?
                                ELSE last_contacted_at
                            END,
                            updated_at = ?
                        WHERE usdot = ?
                        """,
                        (status, merged_notes, status, now, now, usdot),
                    )
            else:
                conn.execute(
                    """
                    INSERT INTO lead_state
                        (usdot, status, notes, follow_up_at, last_contacted_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        usdot,
                        status,
                        merged_notes,
                        follow_up_at,
                        now if status in {"contacted", "interested", "follow_up"} else None,
                        now,
                    ),
                )
            self._log(conn, usdot, status, merged_notes or "")
            conn.commit()

    def mark_viewed(self, usdot: str) -> None:
        with self._connect() as conn:
            self._log(conn, usdot, "viewed")
            conn.commit()

    def _excluded_usdots(self, conn: sqlite3.Connection) -> set[str]:
        rows = conn.execute(
            """
            SELECT usdot FROM lead_state
            WHERE status IN ('skipped','contacted','interested','follow_up','closed_won','closed_lost')
            """
        ).fetchall()
        return {r["usdot"] for r in rows}

    def next_best(self, limit: int = 1) -> list[Lead]:
        with self._connect() as conn:
            excluded = self._excluded_usdots(conn)
        ranked = sorted(
            (lead for lead in self.leads.values() if lead.usdot not in excluded),
            key=lambda lead: (-lead.effective_score, -lead.power_units, lead.company),
        )
        return ranked[:limit]

    def high_score(self, limit: int = 10) -> list[tuple[Lead, str]]:
        with self._connect() as conn:
            statuses = {
                r["usdot"]: r["status"]
                for r in conn.execute("SELECT usdot, status FROM lead_state")
            }
        ranked = sorted(
            self.leads.values(),
            key=lambda lead: (-lead.effective_score, -lead.power_units, lead.company),
        )
        out: list[tuple[Lead, str]] = []
        for lead in ranked:
            status = statuses.get(lead.usdot, "new")
            if status == "skipped":
                continue
            out.append((lead, status))
            if len(out) >= limit:
                break
        return out

    def search(self, query: str, limit: int = 8) -> list[Lead]:
        q = query.strip().lower()
        if not q:
            return []
        hits: list[tuple[int, Lead]] = []
        for lead in self.leads.values():
            blob = " ".join(
                [
                    lead.company,
                    lead.legal_name,
                    lead.usdot,
                    lead.city,
                    lead.state,
                    lead.officer,
                    lead.classdef,
                ]
            ).lower()
            if q not in blob:
                continue
            boost = 20 if lead.company.lower().startswith(q) else 0
            hits.append((lead.effective_score + boost, lead))
        hits.sort(key=lambda item: (-item[0], item[1].company))
        return [lead for _, lead in hits[:limit]]

    def followups_due(self, limit: int = 20) -> list[tuple[Lead, sqlite3.Row]]:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM lead_state
                WHERE status = 'follow_up'
                  AND follow_up_at IS NOT NULL
                  AND follow_up_at <= ?
                ORDER BY follow_up_at ASC
                LIMIT ?
                """,
                (now, limit),
            ).fetchall()
            upcoming = conn.execute(
                """
                SELECT * FROM lead_state
                WHERE status = 'follow_up'
                ORDER BY COALESCE(follow_up_at, updated_at) ASC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        # Prefer due items; if none due yet, show upcoming follow-ups
        chosen = rows if rows else upcoming
        out: list[tuple[Lead, sqlite3.Row]] = []
        for row in chosen:
            lead = self.leads.get(row["usdot"])
            if lead:
                out.append((lead, row))
        return out

    def stats(self) -> dict[str, int]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT status, COUNT(*) AS n FROM lead_state GROUP BY status"
            ).fetchall()
            viewed = conn.execute(
                "SELECT COUNT(DISTINCT usdot) AS n FROM events WHERE action = 'viewed'"
            ).fetchone()["n"]
            due = conn.execute(
                """
                SELECT COUNT(*) AS n FROM lead_state
                WHERE status = 'follow_up'
                  AND follow_up_at IS NOT NULL
                  AND follow_up_at <= ?
                """,
                (datetime.now(timezone.utc).isoformat(),),
            ).fetchone()["n"]
        by_status = {r["status"]: r["n"] for r in rows}
        touched = sum(by_status.values())
        return {
            "total_leads": len(self.leads),
            "touched": touched,
            "new_remaining": max(0, len(self.leads) - len(self._excluded_usdots(self._connect()))),
            "viewed": viewed,
            "contacted": by_status.get("contacted", 0),
            "interested": by_status.get("interested", 0),
            "follow_up": by_status.get("follow_up", 0),
            "follow_up_due": due,
            "skipped": by_status.get("skipped", 0),
            "closed_won": by_status.get("closed_won", 0),
            "closed_lost": by_status.get("closed_lost", 0),
            "telegram_links": self.count_telegram_links(),
        }

    def count_telegram_links(self) -> int:
        with self._connect() as conn:
            return conn.execute("SELECT COUNT(*) AS n FROM telegram_by_phone").fetchone()["n"]

    def find_leads_by_phone(self, phone: str, limit: int = 10) -> list[Lead]:
        keys = phone_match_keys(phone)
        if not keys:
            return []
        hits: list[Lead] = []
        for lead in self.leads.values():
            if phone_match_keys(lead.phone) & keys:
                hits.append(lead)
                if len(hits) >= limit:
                    break
        return hits

    def set_telegram_for_phone(
        self,
        phone: str,
        *,
        telegram_user_id: int | None = None,
        telegram_username: str = "",
        usdot: str = "",
        source: str = "manual",
    ) -> str:
        phone_norm = normalize_phone(phone)
        if not phone_norm:
            raise ValueError("Invalid phone number")
        if telegram_user_id is None and not telegram_username:
            raise ValueError("Provide a Telegram user id or @username")
        username = telegram_username.lstrip("@").strip()
        # Auto-attach first matching lead USDOT if not provided
        if not usdot:
            matches = self.find_leads_by_phone(phone_norm, limit=1)
            if matches:
                usdot = matches[0].usdot
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO telegram_by_phone
                    (phone_norm, telegram_user_id, telegram_username, display_phone, usdot, source, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(phone_norm) DO UPDATE SET
                    telegram_user_id = excluded.telegram_user_id,
                    telegram_username = excluded.telegram_username,
                    display_phone = excluded.display_phone,
                    usdot = CASE
                        WHEN excluded.usdot != '' THEN excluded.usdot
                        ELSE telegram_by_phone.usdot
                    END,
                    source = excluded.source,
                    updated_at = excluded.updated_at
                """,
                (
                    phone_norm,
                    telegram_user_id,
                    username,
                    phone.strip(),
                    usdot,
                    source,
                    self._now(),
                ),
            )
            self._log(
                conn,
                usdot or phone_norm,
                "telegram_linked",
                f"phone={phone_norm}; tg_id={telegram_user_id}; @{username}",
            )
            conn.commit()
        return phone_norm

    def get_telegram_by_phone(self, phone: str) -> sqlite3.Row | None:
        keys = phone_match_keys(phone)
        if not keys:
            return None
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM telegram_by_phone").fetchall()
        for row in rows:
            if row["phone_norm"] in keys or phones_equal(row["display_phone"], phone):
                return row
            # also compare normalized forms
            if phone_match_keys(row["phone_norm"]) & keys:
                return row
        return None

    def get_telegram_for_lead(self, usdot: str) -> sqlite3.Row | None:
        lead = self.get_lead(usdot)
        with self._connect() as conn:
            by_usdot = conn.execute(
                "SELECT * FROM telegram_by_phone WHERE usdot = ? LIMIT 1", (usdot,)
            ).fetchone()
            if by_usdot:
                return by_usdot
        if lead and lead.phone:
            return self.get_telegram_by_phone(lead.phone)
        return None

    def list_telegram_links(self, limit: int = 20) -> list[sqlite3.Row]:
        with self._connect() as conn:
            return conn.execute(
                """
                SELECT * FROM telegram_by_phone
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

    def iter_all(self) -> Iterable[Lead]:
        return self.leads.values()
