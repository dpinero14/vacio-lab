import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString

from vlab.figures import animated_map, national_series, route_series, series_figure


def _tramos():
    filas = []
    for anio, ab in ((2018, 100.0), (2025, 300.0)):
        filas += [{"anio": anio, "id": 1, "km": 100.0, "etiqueta": "RN 152", "provincia": "LA PAMPA", "ab": ab, "ba": 50.0, "total": ab + 50, "total_arena": ab - 100, "vacio": ab - 50, "vacio_km": (ab - 50) * 100, "pct_vacio": 100 * (ab - 50) / (ab + 50)},
                  {"anio": anio, "id": 2, "km": 50.0, "etiqueta": "RN 5", "provincia": "BUENOS AIRES", "ab": 80.0, "ba": 80.0, "total": 160.0, "total_arena": 0.0, "vacio": 0.0, "vacio_km": 0.0, "pct_vacio": 0.0}]
    return pd.DataFrame(filas)


def _net():
    return gpd.GeoDataFrame({"id": [1, 2]}, geometry=[LineString([(-66, -38), (-65, -37)]), LineString([(-65, -37), (-60, -35)])], crs="EPSG:4326")


def test_series_nacional_y_por_ruta():
    n = national_series(_tramos())
    assert bool(n.loc[2018, "medido"]) and not bool(n.loc[2025, "medido"])
    assert n.loc[2025, "vacios_km"] > n.loc[2018, "vacios_km"]
    r = route_series(_tramos(), ("RN 152", "RN 5"))
    assert r.loc[2025, "RN 152"] > r.loc[2018, "RN 152"] and r.loc[2018, "RN 5"] == 0.0


def test_figuras(tmp_path):
    f = series_figure(_tramos(), tmp_path / "s.png", rutas=("RN 152", "RN 5"))
    g = animated_map(_tramos(), _net(), tmp_path / "m.gif", min_total=0.0)
    assert f.stat().st_size > 10000 and g.stat().st_size > 1000
