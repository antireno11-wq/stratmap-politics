from __future__ import annotations

import unittest
from unittest.mock import patch

from backend.app.scrapers import senate


class SenateCommitteeResilienceTests(unittest.TestCase):
    def test_memberships_survive_totals_endpoint_failures(self) -> None:
        def fake_backend_get_json(endpoint: str, params=None):  # type: ignore[no-untyped-def]
            if endpoint == senate.PARLIAMENTARIAN_COMMISSIONS_ENDPOINT:
                return {
                    "data": {
                        "total": 1,
                        "data": [
                            {
                                "ID_COMISION": 107,
                                "NOMBRE": "Comision de Hacienda",
                                "CARGO": "Integrante",
                                "DESCRIPCION": "Permanente",
                                "FECHAINI": "2024-01-01",
                                "FECHAFIN": None,
                            }
                        ],
                    }
                }
            if endpoint == senate.PARLIAMENTARIAN_COMMITTEE_ATTENDANCE_ENDPOINT:
                return {"data": {"total": 5, "data": []}}
            if endpoint == senate.COMMISSION_SESSIONS_ENDPOINT:
                raise RuntimeError("temporary upstream error")
            raise AssertionError(f"unexpected endpoint: {endpoint}")

        with patch.object(senate, "ENABLE_COMMITTEE_ATTENDANCE", True):
            with patch("backend.app.scrapers.senate._backend_get_json", side_effect=fake_backend_get_json):
                fields = senate._fetch_committee_fields_for_senator("1461", {}, {}, {})

        self.assertEqual(fields["committee_count"], 1)
        self.assertEqual(len(fields["committee_memberships"]), 1)
        self.assertEqual(fields["committee_sessions_attended"], 5)
        # Fallback: si no hay total por comision, usamos attended para no dejar score en cero injustificadamente.
        self.assertEqual(fields["committee_total_sessions"], 5)

    def test_attendance_survives_commissions_endpoint_failure(self) -> None:
        def fake_backend_get_json(endpoint: str, params=None):  # type: ignore[no-untyped-def]
            if endpoint == senate.PARLIAMENTARIAN_COMMISSIONS_ENDPOINT:
                raise RuntimeError("upstream commissions down")
            if endpoint == senate.PARLIAMENTARIAN_COMMITTEE_ATTENDANCE_ENDPOINT:
                return {"data": {"total": 11, "data": []}}
            raise AssertionError(f"unexpected endpoint: {endpoint}")

        with patch.object(senate, "ENABLE_COMMITTEE_ATTENDANCE", True):
            with patch("backend.app.scrapers.senate._backend_get_json", side_effect=fake_backend_get_json):
                fields = senate._fetch_committee_fields_for_senator("1461", {}, {}, {})

        self.assertIsNone(fields["committee_count"])
        self.assertEqual(fields["committee_sessions_attended"], 11)
        self.assertEqual(fields["committee_total_sessions"], 11)
        self.assertEqual(fields["committee_memberships"], [])


if __name__ == "__main__":
    unittest.main()
