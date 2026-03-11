from __future__ import annotations

import unittest
from unittest.mock import patch

from backend.app.scrapers import senate


class SenateBiographyTests(unittest.TestCase):
    def test_fetch_biography_prefers_trayectoria_html(self) -> None:
        payload = {
            "data": [
                {
                    "attributes": {
                        "slug": "tomas-de-rementeria-venegas-sen",
                        "field_trayectoria": {"processed": "<p>Senador <strong>activo</strong>.</p>"},
                        "body": {"processed": "<p>Body fallback</p>"},
                    }
                }
            ]
        }
        with patch("backend.app.scrapers.senate._backend_get_json", return_value=payload):
            bio, url = senate._fetch_biography_for_senator("1461", "tomas-de-rementeria-venegas-sen")

        self.assertEqual(bio, "Senador activo.")
        self.assertEqual(
            url,
            "https://www.senado.cl/senadoras-y-senadores/listado-de-senadoras-y-senadores/tomas-de-rementeria-venegas-sen",
        )

    def test_fetch_biography_falls_back_to_body(self) -> None:
        payload = {
            "data": [
                {
                    "attributes": {
                        "slug": "juana-perez-sen",
                        "field_trayectoria": {"processed": ""},
                        "body": {"processed": "<p>Biografia <em>desde body</em>.</p>"},
                    }
                }
            ]
        }
        with patch("backend.app.scrapers.senate._backend_get_json", return_value=payload):
            bio, url = senate._fetch_biography_for_senator("9999", "juana-perez-sen")

        self.assertEqual(bio, "Biografia desde body.")
        self.assertEqual(
            url,
            "https://www.senado.cl/senadoras-y-senadores/listado-de-senadoras-y-senadores/juana-perez-sen",
        )

    def test_merge_biographies_uses_cache_key(self) -> None:
        senators = [
            {"external_id": "slug-a-sen", "_senate_id": "11"},
            {"external_id": "slug-a-sen", "_senate_id": "11"},
            {"external_id": "slug-b-sen", "_senate_id": "12"},
        ]
        with patch(
            "backend.app.scrapers.senate._fetch_biography_for_senator",
            side_effect=[
                ("Bio A", "https://www.senado.cl/.../slug-a-sen"),
                ("Bio B", "https://www.senado.cl/.../slug-b-sen"),
            ],
        ) as mocked:
            out = senate._merge_biographies(senators)

        self.assertEqual(mocked.call_count, 2)
        self.assertEqual(out[0]["biografia"], "Bio A")
        self.assertEqual(out[1]["biografia"], "Bio A")
        self.assertEqual(out[2]["biografia"], "Bio B")


if __name__ == "__main__":
    unittest.main()
