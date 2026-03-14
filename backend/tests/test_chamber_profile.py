from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from backend.app.scrapers import chamber


BIO_HTML = """
<html>
  <body>
    <div>Distrito: N° 8</div>
    <div>Región: Región Metropolitana de Santiago</div>
    <div>Partido: Partido Republicano Bancada: Republicanos</div>
    <div>Período: 2026-2030</div>
  </body>
</html>
"""

ATTENDANCE_HTML = """
<html>
  <body>
    <div>Porcentaje de Asistencia 97,5%</div>
  </body>
</html>
"""


class ChamberProfileTests(unittest.TestCase):
    def test_fetch_deputy_detail_from_profile_page_uses_biography_page_for_territory(self) -> None:
        bio_response = Mock()
        bio_response.text = BIO_HTML
        bio_response.raise_for_status.return_value = None

        attendance_response = Mock()
        attendance_response.text = ATTENDANCE_HTML
        attendance_response.raise_for_status.return_value = None

        with patch.object(chamber.requests, "get", side_effect=[bio_response, attendance_response]) as get_mock:
            detail = chamber.fetch_deputy_detail_from_profile_page("1165")

        self.assertIsNotNone(detail)
        self.assertEqual(detail["distrito_circunscripcion"], "Distrito 8")
        self.assertEqual(detail["region"], "Región Metropolitana de Santiago")
        self.assertEqual(detail["partido"], "Partido Republicano")
        self.assertEqual(detail["periodo"], "2026-2030")
        self.assertEqual(detail["asistencia_pct"], 97.5)
        self.assertEqual(get_mock.call_args_list[0].kwargs["params"], {"prmId": "1165"})
        self.assertTrue(get_mock.call_args_list[0].args[0].startswith(chamber.DEPUTY_BIO_URL))
        self.assertTrue(get_mock.call_args_list[1].args[0].startswith(chamber.DEPUTY_ATTENDANCE_URL))


if __name__ == "__main__":
    unittest.main()
