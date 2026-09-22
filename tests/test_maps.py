import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString

from vlab.maps import color_pct, empty_figure, empty_map


def _net():
    return gpd.GeoDataFrame({
        "id": [1, 2], "km": [100.0, 50.0], "etiqueta": ["RN 1", "RN 2"], "provincia": ["A", "B"], "estado": [5.0, 6.0],
        "ab": [10000.0, 6000.0], "ba": [2000.0, 6000.0], "total": [12000.0, 12000.0],
    }, geometry=[LineString([(-64, -38), (-63, -37)]), LineString([(-63, -37), (-62, -36)])], crs="EPSG:4326")


def test_color_por_umbral():
    assert color_pct(0) == "#4caf50" and color_pct(29.9) == "#4caf50" and color_pct(30) == "#fee08b"
    assert color_pct(60) == "#fc8d59" and color_pct(95) == "#d7301f" and color_pct(float("nan")) == "#556570"


def test_mapa_y_figura(tmp_path):
    z = pd.DataFrame({"codigo": ["AAA"], "centroide": ["ZONA A"], "lon": [-63.5], "lat": [-37.5]})
    m = empty_map(_net(), tmp_path / "m.html", zonas=z)
    html = m.read_text(encoding="utf-8")
    assert "sin carga de vuelta" in html and "RN 1" in html and "Zona A" in html
    f = empty_figure(_net(), tmp_path / "f.png")
    assert f.exists() and f.stat().st_size > 10000
