"""Asignar una matriz origen-destino a la red: cada par viaja por el camino más rápido y deja sus camiones en cada tramo, por sentido.

Es lo que hizo la Secretaría de Transporte para 2018, y es lo que hace falta
para llevar las matrices de otros años a la red: la asignación oficial existe
solo para 2018. La red simplificada está conectada de punta a punta con sus
1.731 tramos, así que alcanza con un grafo: nodos en los extremos de cada
tramo, peso el tiempo de un camión (largo sobre velocidad de pesados), y
Dijkstra desde cada zona con carga. El sentido de cada tramo lo da su
geometría: de A (primer vértice) a B (último). La validación contra la
asignación oficial de 2018 dice cuánto se parece este método al de ellos.
"""

from __future__ import annotations

import networkx as nx
import numpy as np
import pandas as pd


def _snap(p: tuple[float, float], snap: float) -> tuple[float, float]:
    return (round(p[0] / snap) * snap, round(p[1] / snap) * snap)


def build_graph(net: pd.DataFrame, snap: float = 0.001, vel_default: float = 60.0) -> tuple[nx.Graph, dict]:
    """Grafo no dirigido de la red; `links` guarda por tramo sus nodos A y B para saber el sentido después.

    Dos tramos que unen los mismos nodos quedan como uno solo, el más rápido; el otro no recibe flujo y se declara.
    """
    G = nx.Graph()
    links = {}
    for _, r in net.iterrows():
        g = r["geometry"]
        parts = list(g.geoms) if hasattr(g, "geoms") else [g]
        a, b = _snap(parts[0].coords[0], snap), _snap(parts[-1].coords[-1], snap)
        vel = float(r["vel_pesados"]) if pd.notna(r.get("vel_pesados")) and float(r.get("vel_pesados") or 0) > 0 else vel_default
        horas = float(r["km"]) / vel
        if G.has_edge(a, b) and G[a][b]["horas"] <= horas:
            links[r["id"]] = (a, b, False)      # duplicado más lento: sin flujo
            continue
        G.add_edge(a, b, horas=horas, km=float(r["km"]), id=r["id"])
        links[r["id"]] = (a, b, True)
    return G, links


def zone_nodes(G: nx.Graph, zonas: pd.DataFrame) -> dict[str, tuple[float, float]]:
    """El nodo de la red más cercano al centroide de cada zona."""
    nodos = np.array(list(G.nodes))
    out = {}
    for _, z in zonas.iterrows():
        d = (nodos[:, 0] - z["lon"]) ** 2 + (nodos[:, 1] - z["lat"]) ** 2
        out[z["codigo"]] = tuple(nodos[int(np.argmin(d))])
    return out


def assign(G: nx.Graph, links: dict, nodos: dict, matrix: pd.DataFrame) -> pd.DataFrame:
    """Camiones por tramo y sentido para una matriz de camiones (origen x destino).

    Cada origen con carga corre un Dijkstra por tiempo; cada par deja sus camiones en
    los tramos de su camino, en el sentido A→B (`ab`) o B→A (`ba`) según cómo los cruza.
    """
    ab = {i: 0.0 for i in links}
    ba = {i: 0.0 for i in links}
    edge_id = {(a, b): G[a][b]["id"] for a, b in G.edges}
    edge_id.update({(b, a): i for (a, b), i in list(edge_id.items())})
    for origen in matrix.index:
        fila = matrix.loc[origen]
        destinos = fila[(fila > 0) & (fila.index != origen)]
        if destinos.empty or origen not in nodos:
            continue
        paths = nx.single_source_dijkstra_path(G, nodos[origen], weight="horas")
        for destino, camiones in destinos.items():
            if destino not in nodos or nodos[destino] not in paths:
                continue
            p = paths[nodos[destino]]
            for u, v in zip(p[:-1], p[1:]):
                i = edge_id[(u, v)]
                a, b, _ = links[i]
                if (u, v) == (a, b):
                    ab[i] += float(camiones)
                else:
                    ba[i] += float(camiones)
    out = pd.DataFrame({"id": list(links), "ab": [ab[i] for i in links], "ba": [ba[i] for i in links]})
    out["total"] = out["ab"] + out["ba"]
    return out


def validate(asignado: pd.DataFrame, net: pd.DataFrame) -> dict:
    """Cuánto se parece la asignación propia a la oficial de 2018: correlación por tramo, camiones-km y sentido.

    El sentido se compara dos veces, con `ab` contra `ab` y con `ab` contra `ba`, para detectar si la
    convención oficial va al revés de la geometría.
    """
    m = net[["id", "km", "ab", "ba", "total"]].merge(asignado, on="id", suffixes=("_of", "_mio"))
    con = m[(m["total_of"] > 0) | (m["total_mio"] > 0)]
    r_total = float(np.corrcoef(con["total_of"], con["total_mio"])[0, 1])
    r_mismo = float(np.corrcoef(np.r_[con["ab_of"], con["ba_of"]], np.r_[con["ab_mio"], con["ba_mio"]])[0, 1])
    r_cruzado = float(np.corrcoef(np.r_[con["ab_of"], con["ba_of"]], np.r_[con["ba_mio"], con["ab_mio"]])[0, 1])
    vkm_of = float((m["total_of"] * m["km"]).sum())
    vkm_mio = float((m["total_mio"] * m["km"]).sum())
    dentro = con[(con["total_of"] > 0) & (con["total_mio"] > 0)]
    ratio = dentro["total_mio"] / dentro["total_of"]
    return {"r_total": round(r_total, 3), "r_sentido_mismo": round(r_mismo, 3), "r_sentido_cruzado": round(r_cruzado, 3),
            "camiones_km_oficial": vkm_of, "camiones_km_propio": vkm_mio, "cociente_km": round(vkm_mio / vkm_of, 3) if vkm_of else float("nan"),
            "tramos_con_flujo_oficial": int((m["total_of"] > 0).sum()), "tramos_con_flujo_propio": int((m["total_mio"] > 0).sum()),
            "pct_tramos_dentro_de_x2": round(100.0 * float(((ratio > 0.5) & (ratio < 2.0)).mean()), 1) if len(ratio) else float("nan")}


def sum_matrices(matrices: dict[tuple[str, str], pd.DataFrame]) -> pd.DataFrame:
    """Una sola matriz con todos los productos sumados, para asignar de una vez."""
    it = iter(matrices.values())
    total = next(it).copy()
    for m in it:
        total = total.add(m, fill_value=0.0)
    return total


__all__ = ["build_graph", "zone_nodes", "assign", "validate", "sum_matrices"]
