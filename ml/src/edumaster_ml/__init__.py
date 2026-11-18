"""Paquete de datos y modelos de EduMaster.ai (§9, §15.1).

Las variables (features) viven en la API (apps/api/app/modules/ml/features.py) y se importan desde aquí,
para que entrenamiento e inferencia calculen exactamente lo mismo.
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
API = REPO / "apps" / "api"
if str(API) not in sys.path:
    sys.path.insert(0, str(API))
