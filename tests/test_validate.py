import geopandas as gpd
from shapely.geometry import LineString, MultiLineString

from vlab import CRS_METRIC
from vlab.validate import by_route, heavy_share, match_links, overall, route_label, validation_figure


def _net():
    # dos tramos de la RN 152 y uno de la RP 1, en grados
    # el tramo 1 pone 200 camiones por día contra un TMDA de 1.000; el 2, 2.000 contra 500: imposible
    return gpd.GeoDataFrame({"id": [1, 2, 3], "etiqueta": ["RN 152", "RN 152", "RP 1"], "ab": [36500.0, 365000.0, 100.0], "ba": [36500.0, 365000.0, 100.0]},
                            geometry=[MultiLineString([[(-64.0, -37.0), (-64.0, -37.2)]]), LineString([(-64.0, -37.6), (-64.0, -37.8)]), LineString([(-63.0, -37.0), (-63.0, -37.2)])],
                            crs="EPSG:4326")


def _tmda():
    g = gpd.GeoDataFrame({"etiqueta": ["RN 152", "RN 152", "RN 152"], "cod": ["0152"] * 3, "tmda": [1000.0, 500.0, 20.0], "descripcio": ["norte", "sur", "lejos"], "anio_tmda": [2017] * 3},
                         geometry=[LineString([(-64.001, -37.0), (-64.001, -37.2)]), LineString([(-64.001, -37.6), (-64.001, -37.8)]), LineString([(-65.0, -37.0), (-65.0, -37.2)])],
                         crs="EPSG:4326")
    return g.to_crs(CRS_METRIC)


def test_etiquetas_de_ruta():
    assert route_label("0152") == "RN 152" and route_label("0007") == "RN 7" and route_label("A001") == "AU 1" and route_label("1V11") == "RN 1V11"


def test_aparea_el_segmento_correcto_y_marca_lo_imposible(tmp_path):
    m = match_links(_net(), _tmda())
    assert m.set_index("id")["tmda"].to_dict() == {1: 1000.0, 2: 500.0}      # la RP 1 no tiene TMDA; cada tramo con su segmento, no con el lejano
    assert (m["dist_m"] < 200).all()
    h = heavy_share(m, _net())
    assert abs(h.set_index("id").loc[1, "cuota_pesados"] - 0.2) < 1e-9
    assert bool(h.set_index("id").loc[2, "imposible"]) and not bool(h.set_index("id").loc[1, "imposible"])
    r = by_route(h, min_links=2).iloc[0]
    assert r["etiqueta"] == "RN 152" and r["n_imposibles"] == 1
    o = overall(h)
    assert o["tramos"] == 2 and o["imposibles"] == 1
    f = validation_figure(h, tmp_path / "v.png")
    assert f.stat().st_size > 10000
