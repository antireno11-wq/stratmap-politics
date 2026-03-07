from __future__ import annotations

from .db import init_db, recalculate_scores, upsert_deputy_snapshots


SEED_DATA = [
    {
        "external_id": "D001",
        "nombre": "Ana Perez",
        "partido": "Partido A",
        "distrito": "Distrito 10",
        "region": "Metropolitana",
        "periodo": "2026-Q1",
        "attendance_pct": 96,
        "sesiones_ausentes": 1,
        "sesiones_totales": 25,
        "votaciones_participadas": 480,
        "votaciones_ausentes": 10,
        "party_alignment_pct": 89,
        "bills_presented": 12,
        "bills_approved": 4,
        "bills_in_progress": 7,
        "lobby_compliance_pct": 98,
        "meetings_registered": 16,
        "official_trips": 3,
        "interventions": 44,
        "commissions": [
            {"name": "Constitucion", "participation_pct": 94},
            {"name": "Hacienda", "participation_pct": 88},
        ],
    },
    {
        "external_id": "D002",
        "nombre": "Carlos Soto",
        "partido": "Partido B",
        "distrito": "Distrito 7",
        "region": "Valparaiso",
        "periodo": "2026-Q1",
        "attendance_pct": 85,
        "sesiones_ausentes": 4,
        "sesiones_totales": 26,
        "votaciones_participadas": 430,
        "votaciones_ausentes": 40,
        "party_alignment_pct": 76,
        "bills_presented": 8,
        "bills_approved": 2,
        "bills_in_progress": 5,
        "lobby_compliance_pct": 81,
        "meetings_registered": 9,
        "official_trips": 1,
        "interventions": 30,
        "commissions": [
            {"name": "Salud", "participation_pct": 80},
            {"name": "Educacion", "participation_pct": 77},
        ],
    },
]


def run_seed() -> None:
    init_db()
    upsert_deputy_snapshots(SEED_DATA)
    recalculate_scores()


if __name__ == "__main__":
    run_seed()
    print("Seed completado")
