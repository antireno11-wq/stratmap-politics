# Stratmap Politics (Base Parlamento)

Primera fase: catalogo de parlamentarios de Chile (diputados + senadores).

## Stack
- Backend: FastAPI + PostgreSQL
- Frontend: Next.js

## Objetivo fase actual
- Ingerir y mostrar parlamentarios por camara.
- No calcular score todavia.
- Agregar metricas en etapas posteriores (asistencia, votaciones, proyectos, lobby).

## Endpoints principales
- `POST /api/v1/ingest/chamber/deputies`
- `POST /api/v1/ingest/senate/senators`
- `POST /api/v1/ingest/all`
- `POST /api/v1/ingest/parliamentarians` (manual)
- `GET /api/v1/parliamentarians`
- `GET /api/v1/parliamentarians/{id}`

## Flujo recomendado (Railway)
1. Deploy backend y frontend.
2. Ejecutar:
   - `POST /api/v1/ingest/chamber/deputies`
   - `POST /api/v1/ingest/senate/senators`
3. Abrir frontend.

## Variables backend
- `DATABASE_URL`
- `AUTO_INGEST_ENABLED=true|false`
- `AUTO_INGEST_INTERVAL_MINUTES=360`
- `CHAMBER_API_BASE` (opcional)
- `SENATE_LIST_URL` (opcional)
