import geopandas as gpd
from shapely.geometry import LineString

from vlab.network import by_route, link_imbalance, summary


def _net():
    return gpd.GeoDataFrame({
        "id": [1, 2, 3], "km": [100.0, 50.0, 10.0], "etiqueta": ["RN 1", "RN 1", "RN 2"], "provincia": ["A", "A", "B"],
        "ab": [1000.0, 300.0, 0.0], "ba": [200.0, 300.0, 0.0], "total": [1200.0, 600.0, 0.0], "estado": [5.0, 6.0, 7.0],
    }, geometry=[LineString([(0, 0), (1, 0)]), LineString([(1, 0), (2, 0)]), LineString([(2, 0), (3, 0)])], crs="EPSG:4326")


def test_link_imbalance():
    n = link_imbalance(_net(), dias=100)
    assert list(n["vacio"]) == [800.0, 0.0, 0.0] and list(n["vacio_dia"]) == [8.0, 0.0, 0.0]
    assert abs(n["pct_vacio"].iloc[0] - 100 * 800 / 1200) < 1e-9 and n["pct_vacio"].isna().iloc[2]
    assert n["vacio_km"].iloc[0] == 80000.0


def test_summary_y_por_ruta():
    s = summary(_net())
    assert s["camiones_km_total"] == 1200 * 100 + 600 * 50 and s["camiones_km_vacios"] == 80000.0 and s["tramos"] == 3
    r = by_route(_net())
    assert r.iloc[0]["etiqueta"] == "RN 1" and r.iloc[0]["vacio_km"] == 80000.0 and r.iloc[0]["km"] == 150.0
