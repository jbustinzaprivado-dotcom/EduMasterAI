# ml/ — Dataset y modelo de riesgo de abandono (Fases 4-5)

| Ruta | Contenido |
|---|---|
| `src/edumaster_ml/generate.py` | Simulador del dataset **sintético DEMO** (D06) y su ficha (datasheet). |
| `src/edumaster_ml/train.py` | Baselines, red multitarea con GRU, calibración, selección (D26) y exportación. |
| `registry/riesgo-abandono/<versión>/` | `model.json` (pesos para la API) y `model_card.json` (métricas, segmentos, límites). |
| `datasets/*.datasheet.json` | Ficha del dataset: definición de la etiqueta, separación temporal y huella SHA-256. |
| `tests/` | Sin fuga de información, etiqueta, reproducibilidad, NumPy = PyTorch. |

Las variables viven en `apps/api/app/modules/ml/features.py`: entrenamiento e inferencia usan el mismo código.

## Reentrenar

```bash
cd ml
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python -m pip install torch==2.15.0 --index-url https://download.pytorch.org/whl/cpu
.venv/Scripts/python -m edumaster_ml.train
```

Una versión nueva se registra sola al reiniciar la API, pero **no se usa hasta que un administrador la aprueba**
en "Modelos de IA" (D23).
