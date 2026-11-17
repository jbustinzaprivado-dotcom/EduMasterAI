"""Metadatos de la arquitectura neuronal para el visualizador (§4.10, §9.1).

En la Fase 1 no hay modelo entrenado: se publica el DISEÑO de la red multitarea con estado "design".
Desde la Fase 5 estos datos saldrán del registro de modelos (MLflow) con versión, dataset y métricas.
"""

from fastapi import APIRouter
from pydantic import BaseModel

from app.api.deps import Principal, require

router = APIRouter(prefix="/ml", tags=["ml"])


class Layer(BaseModel):
    id: str
    name: str
    role: str  # input | projection | hidden | temporal | fusion | output
    display_nodes: int  # nodos que dibuja la interfaz (resumen visual, no el total real)
    units: str
    operation: str
    dimension: str
    detail: list[str]


class Architecture(BaseModel):
    model_name: str
    status: str  # design | stopped | loading | training | validating | published | inference | error
    status_label: str
    version: str | None
    dataset: str | None
    source: str
    note: str
    layers: list[Layer]


_DESIGN = Architecture(
    model_name="EduMaster Multi-Task Learning Network",
    status="design",
    status_label="Diseño · modelo aún no entrenado",
    version=None,
    dataset=None,
    source="Especificación §9.1",
    note="Tamaños propuestos; se ajustan con validación en la Fase 5 y deben superar a los baselines (§9.1).",
    layers=[
        Layer(id="input", name="Entrada", role="input", display_nodes=8, units="8 variables + secuencia",
              operation="Variables agregadas y secuencia de eventos", dimension="[lote, 8] + [lote, 30, 6]",
              detail=["active_days_14d", "sessions_14d", "completion_ratio", "assessment_mean",
                      "assessment_trend", "late_submissions_30d", "content_engagement",
                      "days_since_last_activity"]),
        Layer(id="projection", name="Proyección / embeddings", role="projection", display_nodes=6, units="32",
              operation="Normalización + embeddings categóricos", dimension="[lote, 32]",
              detail=["Escalado de variables numéricas", "Embedding de course_level"]),
        Layer(id="temporal", name="Bloque temporal", role="temporal", display_nodes=6, units="64",
              operation="GRU sobre ventana de 30 días (Transformer si hay volumen)", dimension="[lote, 64]",
              detail=["Captura la evolución del comportamiento", "Rama temporal de §9.1"]),
        Layer(id="fusion", name="Fusión compartida", role="fusion", display_nodes=5, units="128",
              operation="Concatenación + Dense + LayerNorm + Dropout", dimension="[lote, 128]",
              detail=["Combina patrones estáticos y temporales"]),
        Layer(id="heads", name="Cabezas de salida", role="output", display_nodes=4, units="4 tareas",
              operation="Sigmoid / softmax ordinal / ranking", dimension="4 salidas",
              detail=["A · Finalización (sigmoid)", "B · Dominio de competencia (ordinal, 5 niveles)",
                      "C · Riesgo de abandono (sigmoid) — primera en construirse",
                      "D · Ranking de recursos"]),
    ],
)


@router.get("/architecture", response_model=Architecture)
def architecture(_principal: Principal = require("dashboard.read")) -> Architecture:
    return _DESIGN
