"""vacio-lab: el mapa del vacío, cuánto del transporte de cargas argentino vuelve sin carga.

Rutas del repo y constantes. Todo lo demás vive en módulos con funciones puras:
`od` (las matrices origen-destino por zona), `network` (la red vial con el flujo
de camiones por sentido), `imbalance` (el desbalance ida-vuelta por par y por
tramo), `maps` (figuras y mapa interactivo).
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_RAW = REPO_ROOT / "data" / "raw"
DATA_PROC = REPO_ROOT / "data" / "processed"
DOCS = REPO_ROOT / "docs"
FIGURES = DOCS / "figures"

# Los años con matriz publicada por la Secretaría de Transporte.
ANIOS = (2012, 2014, 2016, 2018)

# Los ocho grupos de producto de la matriz, con el nombre de archivo que usa cada uno.
GRUPOS = ("ganado en pie", "carnes", "granos", "regionales", "semiterminados", "industrializados", "mineria", "combustibles")

# Sistema proyectado para medir en metros sobre todo el país: POSGAR 2007 faja 4 (centro, Córdoba y Buenos Aires).
CRS_METRIC = "EPSG:5346"
CRS_GEO = "EPSG:4326"

__all__ = ["REPO_ROOT", "DATA_RAW", "DATA_PROC", "DOCS", "FIGURES", "ANIOS", "GRUPOS", "CRS_METRIC", "CRS_GEO"]
