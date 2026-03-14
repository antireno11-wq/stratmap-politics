from __future__ import annotations

import unittest

from backend.app import db


class DbPublicMergeTests(unittest.TestCase):
    def test_merge_preserves_existing_public_fields_when_incoming_is_missing(self) -> None:
        merged = db._merge_existing_public_fields(
            {
                "external_id": "1165",
                "partido": "Partido Republicano",
                "distrito_circunscripcion": "Sin dato",
                "region": "Sin dato",
                "periodo": "Sin dato",
                "biografia": None,
                "biografia_url": None,
            },
            {
                "external_id": "1165",
                "partido": "Partido Republicano",
                "distrito_circunscripcion": "Distrito 8",
                "region": "Región Metropolitana de Santiago",
                "periodo": "2026-2030",
                "biografia": "Bio existente",
                "biografia_url": "https://www.camara.cl/diputados/detalle/biografia.aspx?prmId=1165",
            },
        )

        self.assertEqual(merged["distrito_circunscripcion"], "Distrito 8")
        self.assertEqual(merged["region"], "Región Metropolitana de Santiago")
        self.assertEqual(merged["periodo"], "2026-2030")
        self.assertEqual(merged["biografia"], "Bio existente")
        self.assertEqual(
            merged["biografia_url"],
            "https://www.camara.cl/diputados/detalle/biografia.aspx?prmId=1165",
        )

    def test_merge_prefers_new_public_fields_when_present(self) -> None:
        merged = db._merge_existing_public_fields(
            {
                "external_id": "1165",
                "partido": "Partido Republicano",
                "distrito_circunscripcion": "Distrito 8",
                "region": "Región Metropolitana de Santiago",
                "periodo": "2026-2030",
                "biografia": "Bio nueva",
                "biografia_url": "https://example.com/nueva",
            },
            {
                "external_id": "1165",
                "partido": "Sin dato",
                "distrito_circunscripcion": "Sin dato",
                "region": "Sin dato",
                "periodo": "Sin dato",
                "biografia": "Bio vieja",
                "biografia_url": "https://example.com/vieja",
            },
        )

        self.assertEqual(merged["distrito_circunscripcion"], "Distrito 8")
        self.assertEqual(merged["region"], "Región Metropolitana de Santiago")
        self.assertEqual(merged["biografia"], "Bio nueva")
        self.assertEqual(merged["biografia_url"], "https://example.com/nueva")


if __name__ == "__main__":
    unittest.main()
