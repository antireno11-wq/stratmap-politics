from __future__ import annotations

import unittest
from unittest.mock import patch

from backend.app.scrapers import chamber


SESSION_XML = b"""<?xml version="1.0" encoding="utf-8"?>
<SesionSala xmlns="http://opendata.camara.cl/camaradiputados/v1">
  <Id>4754</Id>
  <Estado Valor="1">Celebrada</Estado>
  <Votaciones>
    <Votacion>
      <Id>87794</Id>
    </Votacion>
    <Votacion>
      <Id>87793</Id>
    </Votacion>
  </Votaciones>
  <ListadoAsistencia>
    <Asistencia>
      <TipoAsistencia Valor="1">Asiste</TipoAsistencia>
      <Diputado>
        <Id>1115</Id>
        <Nombre>Mercedes</Nombre>
        <ApellidoPaterno>Bulnes</ApellidoPaterno>
        <ApellidoMaterno>Nunez</ApellidoMaterno>
      </Diputado>
    </Asistencia>
    <Asistencia>
      <TipoAsistencia Valor="0">No Asiste</TipoAsistencia>
      <Diputado>
        <Id>1124</Id>
        <Nombre>Tomas</Nombre>
        <ApellidoPaterno>De Rementeria</ApellidoPaterno>
        <ApellidoMaterno>Venegas</ApellidoMaterno>
      </Diputado>
    </Asistencia>
  </ListadoAsistencia>
</SesionSala>
"""

VOTE_87794_XML = b"""<?xml version="1.0" encoding="utf-8"?>
<Votacion xmlns="http://opendata.camara.cl/camaradiputados/v1">
  <Id>87794</Id>
  <Votos>
    <Voto>
      <Diputado>
        <Id>1115</Id>
        <Nombre>Mercedes</Nombre>
        <ApellidoPaterno>Bulnes</ApellidoPaterno>
        <ApellidoMaterno>Nunez</ApellidoMaterno>
      </Diputado>
      <OpcionVoto Valor="1">Afirmativo</OpcionVoto>
    </Voto>
  </Votos>
</Votacion>
"""

VOTE_87793_XML = b"""<?xml version="1.0" encoding="utf-8"?>
<Votacion xmlns="http://opendata.camara.cl/camaradiputados/v1">
  <Id>87793</Id>
  <Votos>
    <Voto>
      <Diputado>
        <Id>9999</Id>
        <Nombre>Otra</Nombre>
        <ApellidoPaterno>Persona</ApellidoPaterno>
        <ApellidoMaterno>Demo</ApellidoMaterno>
      </Diputado>
      <OpcionVoto Valor="2">Negativo</OpcionVoto>
    </Voto>
  </Votos>
</Votacion>
"""


class ChamberVotingTests(unittest.TestCase):
    def test_fetch_voting_stats_uses_only_votes_from_attended_sessions(self) -> None:
        def fake_request_xml(path: str, params=None):
            if path.endswith("retornarSesionAsistencia"):
                return SESSION_XML
            if path.endswith("retornarVotacionDetalle") and params and params.get("prmVotacionId") == 87794:
                return VOTE_87794_XML
            if path.endswith("retornarVotacionDetalle") and params and params.get("prmVotacionId") == 87793:
                return VOTE_87793_XML
            raise AssertionError(f"Unexpected request: {path} {params}")

        with patch.object(chamber, "fetch_sessions", return_value=[{"session_id": 4754, "fecha": None}]):
            with patch.object(chamber, "_request_xml", side_effect=fake_request_xml):
                with patch.object(chamber, "_build_valid_deputy_name_set", return_value={"mercedes bulnes nunez"}):
                    stats_by_id, stats_by_name = chamber.fetch_voting_stats_by_deputy(2026, 2026, 50)

        self.assertEqual(stats_by_id["1115"]["votes_expected"], 2)
        self.assertEqual(stats_by_id["1115"]["votes_cast"], 1)
        self.assertEqual(stats_by_id["1115"]["votes_yes"], 1)
        self.assertEqual(stats_by_id["1115"]["votes_no"], 0)
        self.assertEqual(stats_by_id["1115"]["votes_abstention"], 0)
        self.assertEqual(stats_by_name["mercedes bulnes nunez"]["votes_expected"], 2)
        self.assertEqual(stats_by_name["mercedes bulnes nunez"]["votes_cast"], 1)
        self.assertEqual(stats_by_name["mercedes bulnes nunez"]["votes_yes"], 1)
        self.assertNotIn("1124", stats_by_id)


if __name__ == "__main__":
    unittest.main()
