from __future__ import annotations

import unittest
from unittest.mock import patch

from backend.app.scrapers import senate


class SenateVotingTests(unittest.TestCase):
    def test_fetch_voting_stats_aggregates_votes_by_legislature(self) -> None:
        def fake_backend_get_json(endpoint: str, params=None):  # type: ignore[no-untyped-def]
            params = params or {}
            if endpoint == senate.SESSIONS_ENDPOINT:
                return {
                    "data": {
                        "total": 2,
                        "data": [
                            {
                                "ID_SESION": 10114,
                                "ID_LEGISLATURA": 505,
                                "FECHA": "04/03/2026",
                            },
                            {
                                "ID_SESION": 10122,
                                "ID_LEGISLATURA": 507,
                                "FECHA": "10/03/2026",
                            },
                        ],
                    }
                }
            if endpoint == senate.VOTES_ENDPOINT and int(params.get("id_legislatura") or 0) == 505:
                return {
                    "data": {
                        "total": 2,
                        "data": [
                            {
                                "ID_VOTACION": 10915,
                                "ID_SESION": 10114,
                                "FECHA_VOTACION": "04-03-2026 20:47:26",
                                "VOTACIONES": {
                                    "SI": [
                                        {
                                            "PARLID": 1461,
                                            "SLUG": "tomas-de-rementeria-venegas-sen",
                                            "NOMBRE": "Tomás",
                                            "APELLIDO_PATERNO": "De Rementería",
                                            "APELLIDO_MATERNO": "Venegas",
                                        }
                                    ],
                                    "NO": [],
                                    "ABSTENCION": [],
                                    "PAREO": [],
                                },
                            },
                            {
                                "ID_VOTACION": 10914,
                                "ID_SESION": 10114,
                                "FECHA_VOTACION": "04-03-2026 20:41:39",
                                "VOTACIONES": {
                                    "SI": [],
                                    "NO": [
                                        {
                                            "PARLID": 1461,
                                            "SLUG": "tomas-de-rementeria-venegas-sen",
                                            "NOMBRE": "Tomás",
                                            "APELLIDO_PATERNO": "De Rementería",
                                            "APELLIDO_MATERNO": "Venegas",
                                        }
                                    ],
                                    "ABSTENCION": [],
                                    "PAREO": [],
                                },
                            },
                        ],
                    }
                }
            if endpoint == senate.VOTES_ENDPOINT and int(params.get("id_legislatura") or 0) == 507:
                return {"data": {"total": 1, "data": []}}
            raise AssertionError(f"unexpected endpoint: {endpoint} {params}")

        with patch("backend.app.scrapers.senate._backend_get_json", side_effect=fake_backend_get_json):
            by_id, by_slug, by_name = senate.fetch_voting_stats_by_senator(2026)

        self.assertEqual(by_id["1461"]["votes_expected"], 2)
        self.assertEqual(by_id["1461"]["votes_cast"], 2)
        self.assertEqual(by_id["1461"]["votes_yes"], 1)
        self.assertEqual(by_id["1461"]["votes_no"], 1)
        self.assertEqual(by_id["1461"]["votes_abstention"], 0)
        self.assertEqual(by_slug["tomas-de-rementeria-venegas-sen"]["votes_expected"], 2)
        self.assertEqual(by_name["tomas de rementeria venegas"]["votes_cast"], 2)

    def test_merge_voting_fields_prefers_senate_id(self) -> None:
        senators = [
            {
                "external_id": "tomas-de-rementeria-venegas-sen",
                "nombre": "Tomás De Rementería Venegas",
                "_senate_id": "1461",
                "votes_cast_total": None,
                "votes_expected_total": None,
                "voting_participation_pct": None,
                "votes_yes_total": None,
                "votes_no_total": None,
                "votes_abstention_total": None,
            }
        ]

        with patch(
            "backend.app.scrapers.senate.fetch_voting_stats_by_senator",
            return_value=(
                {"1461": {"votes_cast": 6, "votes_expected": 8, "votes_yes": 4, "votes_no": 1, "votes_abstention": 1}},
                {},
                {},
            ),
        ):
            out = senate._merge_voting_fields(senators)

        self.assertEqual(out[0]["votes_cast_total"], 6)
        self.assertEqual(out[0]["votes_expected_total"], 8)
        self.assertEqual(out[0]["voting_participation_pct"], 75.0)
        self.assertEqual(out[0]["votes_yes_total"], 4)
        self.assertEqual(out[0]["votes_no_total"], 1)
        self.assertEqual(out[0]["votes_abstention_total"], 1)


if __name__ == "__main__":
    unittest.main()
