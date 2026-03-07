# Stratmap Politics (MVP)

Plataforma para medir transparencia y actividad de diputados en Chile con datos publicos.

## Stack
- Backend: FastAPI + PostgreSQL
- Frontend: Next.js
- Scraping: Requests + Playwright + BeautifulSoup

## Estructura
- `backend/app/main.py`: API principal y job automatico
- `backend/app/db.py`: esquema y consultas
- `backend/app/scoring.py`: formula de score (0-100)
- `backend/app/scrapers/chamber.py`: scraper real de `opendata.camara.cl`
- `backend/app/ingest.py`: pipeline de ingesta + recalculo
- `backend/app/seed.py`: carga de datos demo
- `frontend/app/page.tsx`: dashboard ranking
- `frontend/app/deputies/[id]/page.tsx`: perfil individual

## Formula del score (v1)
`Total = Asistencia*0.30 + Votaciones*0.20 + ActividadLegislativa*0.25 + Transparencia*0.15 + Comisiones*0.10`

## Ejecutar con Docker
```bash
cd stratmap-politics
docker compose up --build
```

Servicios:
- Frontend: `http://localhost:3000`
- API: `http://localhost:8000`

Con `docker-compose` actual:
- `AUTO_INGEST_ENABLED=true`
- ingesta automatica cada `360` minutos (6 horas)

## Ingesta real desde Camara
### Disparo manual
```bash
curl -X POST 'http://localhost:8000/api/v1/ingest/chamber?year=2026&session_limit=80'
```

### Estado del job automatico
```bash
curl 'http://localhost:8000/api/v1/ingest/status'
```

## Ejecutar local sin Docker
### 1) Backend
```bash
cd stratmap-politics/backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL='postgresql://stratmap:stratmap@localhost:5432/stratmap'
export AUTO_INGEST_ENABLED=true
export AUTO_INGEST_INTERVAL_MINUTES=360
uvicorn app.main:app --reload
```

### 2) Frontend
```bash
cd stratmap-politics/frontend
npm install
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

## Endpoints MVP
- `POST /api/v1/ingest/chamber`
- `GET /api/v1/ingest/status`
- `POST /api/v1/ingest/deputies`
- `POST /api/v1/scores/recalculate`
- `GET /api/v1/ranking`
- `GET /api/v1/deputies/{id}`

## Fuentes oficiales conectadas
- `WSDiputado.asmx/retornarDiputadosPeriodoActual`
- `WSSala.asmx/retornarSesionesXAnno`
- `WSSala.asmx/retornarSesionAsistencia`
- `WSComision.asmx/retornarComisionesVigentes`

Nota: este primer scraper usa asistencia y comisiones reales; las otras metricas quedan en 0 hasta conectar modulos de votaciones, proyectos de ley y lobby.
