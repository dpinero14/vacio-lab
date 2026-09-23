import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString

from vlab.assign import assign, build_graph, sum_matrices, validate, zone_nodes


def _net():
    # tres tramos en línea: N0 -(1)- N1 -(2)- N2 -(3)- N3, y un atajo lento paralelo al 2
    return gpd.GeoDataFrame({
        "id": [1, 2, 3, 4], "km": [100.0, 100.0, 100.0, 100.0], "vel_pesados": [80.0, 80.0, 80.0, 20.0],
        "ab": [10.0, 10.0, 2.0, 0.0], "ba": [3.0, 3.0, 0.0, 0.0], "total": [13.0, 13.0, 2.0, 0.0],
    }, geometry=[LineString([(0, 0), (1, 0)]), LineString([(1, 0), (2, 0)]), LineString([(2, 0), (3, 0)]), LineString([(1, 0), (1, 1), (2, 0)])], crs="EPSG:4326")


def _zonas():
    return pd.DataFrame({"codigo": ["AAA", "BBB"], "lon": [0.01, 2.02], "lat": [0.0, 0.0]})


def test_grafo_conectado_y_duplicado_sin_flujo():
    G, links = build_graph(_net())
    assert G.number_of_nodes() == 4 and G.number_of_edges() == 3
    assert links[4][2] is False and links[2][2] is True       # el atajo lento no recibe flujo


def test_asignacion_por_sentido():
    G, links = build_graph(_net()); nodos = zone_nodes(G, _zonas())
    m = pd.DataFrame([[0, 10], [3, 0]], index=["AAA", "BBB"], columns=["AAA", "BBB"], dtype=float)
    a = assign(G, links, nodos, m).set_index("id")
    assert a.loc[1, "ab"] == 10 and a.loc[1, "ba"] == 3 and a.loc[2, "ab"] == 10 and a.loc[2, "ba"] == 3
    assert a.loc[3, "total"] == 0 and a.loc[4, "total"] == 0


def test_validacion_contra_oficial():
    G, links = build_graph(_net()); nodos = zone_nodes(G, _zonas())
    m = pd.DataFrame([[0, 10], [3, 0]], index=["AAA", "BBB"], columns=["AAA", "BBB"], dtype=float)
    v = validate(assign(G, links, nodos, m), _net())
    assert v["r_total"] > 0.99 and abs(v["cociente_km"] - 26 / 28) < 1e-3 and v["r_sentido_mismo"] > v["r_sentido_cruzado"]
    assert v["tramos_con_flujo_oficial"] == 3 and v["tramos_con_flujo_propio"] == 2


def test_sum_matrices():
    a = pd.DataFrame([[0, 1], [0, 0]], index=["A", "B"], columns=["A", "B"], dtype=float)
    s = sum_matrices({("g", "x"): a, ("g", "y"): a * 2})
    assert s.loc["A", "B"] == 3
