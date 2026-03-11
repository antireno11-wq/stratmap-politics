from __future__ import annotations

import unittest

from backend.app.scoring import calc_committee_score, calc_public_score, calc_scores


class CommitteeScoringTests(unittest.TestCase):
    def test_committee_score_with_full_metrics(self) -> None:
        metrics = {
            "committee_sessions_attended": 80,
            "committee_total_sessions": 100,
            "committee_count": 4,
            "chamber_average_committee_count": 2,
            "committee_memberships": [
                {"committee_name": "Comision de Hacienda", "role": "President"},
                {"committee_name": "Comision de Educacion", "role": "Vice President"},
                {"committee_name": "Comision de Salud", "role": "Full member"},
                {"committee_name": "Comision de Trabajo", "role": "Substitute member"},
            ],
            "committee_activity_bills_discussed": 20,
            "committee_activity_bills_sponsored": 5,
            "committee_activity_interventions": 10,
            "committee_topic_counts": {"economia_hacienda": 3, "social_educacion_salud": 1},
        }
        result = calc_committee_score(metrics)
        breakdown = result["committee_score_breakdown"]

        self.assertAlmostEqual(result["committee_score"], 83.62, places=2)
        self.assertAlmostEqual(
            breakdown["normalized"]["committee_attendance_score"],
            80.0,
            places=2,
        )
        self.assertAlmostEqual(
            breakdown["normalized"]["committee_count_score"],
            100.0,
            places=2,
        )
        self.assertAlmostEqual(
            breakdown["normalized"]["committee_role_score"],
            73.75,
            places=2,
        )
        self.assertAlmostEqual(
            breakdown["normalized"]["committee_activity_score"],
            87.5,
            places=2,
        )
        self.assertAlmostEqual(
            breakdown["normalized"]["specialization_score"],
            75.0,
            places=2,
        )

    def test_committee_score_handles_missing_activity_safely(self) -> None:
        metrics = {
            "committee_sessions_attended": 10,
            "committee_total_sessions": 20,
            "committee_memberships": [
                {"committee_name": "Comision de Seguridad", "role": "Integrante"},
                {"committee_name": "Comision de Defensa", "role": "Integrante"},
            ],
            "committee_count": 2,
            "chamber_average_committee_count": 4,
            "committee_activity_bills_discussed": None,
            "committee_activity_bills_sponsored": None,
            "committee_activity_interventions": None,
        }
        result = calc_committee_score(metrics)
        breakdown = result["committee_score_breakdown"]

        self.assertIsNone(breakdown["normalized"]["committee_activity_score"])
        self.assertFalse(breakdown["components"]["committee_activity"]["applicable"])
        self.assertIsNone(
            breakdown["raw"]["committee_activity_index"],
        )
        self.assertIsNotNone(result["committee_score"])
        self.assertGreaterEqual(result["committee_score"], 0.0)
        self.assertLessEqual(result["committee_score"], 100.0)

    def test_total_scoring_includes_committee_component(self) -> None:
        metrics = {
            "attendance_pct": 90,
            "voting_participation_pct": 50,
            "party_alignment_pct": 50,
            "bills_presented": 4,
            "bills_approved": 1,
            "bills_in_progress": 2,
            "lobby_compliance_pct": 90,
            "meetings_registered": 2,
            "official_trips": 1,
            "committee_sessions_attended": 30,
            "committee_total_sessions": 40,
            "committee_count": 3,
            "chamber_average_committee_count": 2,
            "committee_memberships": [
                {"committee_name": "Comision de Hacienda", "role": "Presidente"},
                {"committee_name": "Comision de Economia", "role": "Integrante"},
                {"committee_name": "Comision de Mineria", "role": "Integrante"},
            ],
        }
        result = calc_scores(metrics)
        self.assertIn("committee_score", result)
        self.assertIn("committee_score_breakdown", result)
        self.assertIn("commissions_score", result)
        self.assertIn("components", result)
        self.assertAlmostEqual(result["committee_score"], result["commissions_score"], places=2)
        self.assertTrue(result["components"]["committees"]["applicable"])

    def test_total_scoring_excludes_non_applicable_components(self) -> None:
        metrics = {
            "attendance_pct": 84,
            "voting_participation_pct": None,
            "party_alignment_pct": None,
            "bills_presented": None,
            "bills_approved": None,
            "bills_in_progress": None,
            "lobby_compliance_pct": None,
            "meetings_registered": None,
            "official_trips": None,
            "committee_memberships": [],
            "committee_count": 0,
        }
        result = calc_scores(metrics)
        self.assertEqual(result["total_score"], 84.0)
        self.assertTrue(result["components"]["attendance"]["applicable"])
        self.assertFalse(result["components"]["committees"]["applicable"])

    def test_public_score_marks_committee_not_applicable(self) -> None:
        payload = calc_public_score({"attendance_pct": 90, "committee_score": None})
        self.assertEqual(payload["final_score"], 90.0)
        self.assertTrue(payload["components"]["attendance"]["applicable"])
        self.assertFalse(payload["components"]["committees"]["applicable"])


if __name__ == "__main__":
    unittest.main()
