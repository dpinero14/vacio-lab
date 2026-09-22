"""La red vial simplificada de 2018 con el flujo de camiones asignado por sentido.

Cada tramo trae `ab_flow` y `ba_flow`: camiones por año en cada sentido, según
la asignación de la matriz a la red que hizo la Secretaría de Transporte. La
diferencia entre los dos es el vacío estructural del tramo: camiones que en un
sentido van cargados y en el otro no tienen qué llevar. También trae el estado
del pavimento, que se usa para cruzar vacío con deterioro.
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

from . import CRS_GEO, DATA_RAW, GRUPOS

COLUMNAS = {"length": "km", "ruta": "ruta", "jurisdic": "jurisdiccion", "etiqueta_r": "etiqueta", "provincia": "provincia",
            "material": "material", "estado": "estado", "rugosidad": "rugosidad", "ahuellamie": "ahuellamiento", "vel_pes": "vel_pesados"}


def _layer_name(grupo: str | None) -> str:
    if grupo is None:
        return "red_total_2018.geojson"
    g = grupo.lower().replace("í", "i").replace(" ", "_")
    return f"red_{'grupo_' if g != 'semiterminados' else ''}{g}_2018.geojson"


def load_network(grupo: str | None = None, raw: Path = DATA_RAW) -> gpd.GeoDataFrame:
    """Los 1.731 tramos con ida, vuelta y total en camiones por año, para el total o para un grupo."""
    g = gpd.read_file(raw / _layer_name(grupo)).set_crs(CRS_GEO, allow_override=True)
    pref = [c for c in g.columns if c.endswith("_ab_flow")][0].replace("_ab_flow", "")
    out = g.rename(columns={**COLUMNAS, f"{pref}_ab_flow": "ab", f"{pref}_ba_flow": "ba", f"{pref}_tot_flow": "total"})
    keep = ["id", "km", "ruta", "jurisdiccion", "etiqueta", "provincia", "material", "estado", "rugosidad", "ahuellamiento", "vel_pesados", "ab", "ba", "total", "geometry"]
    out = out[[c for c in keep if c in out.columns]].copy()
    for c in ("ab", "ba", "total", "km"):
        out[c] = pd.to_numeric(out[c], errors="coerce").fillna(0.0)
    out["grupo"] = grupo or "total"
    return gpd.GeoDataFrame(out, geometry="geometry", crs=CRS_GEO)


def link_imbalance(net: gpd.GeoDataFrame, dias: int = 300) -> gpd.GeoDataFrame:
    """Por tramo: el sentido cargado, el vacío en camiones por año y por día, y la fracción del tránsito que vuelve vacía.

    `vacio` = |ida - vuelta|: los camiones que cruzan el tramo en el sentido mayor y no
    tienen carga equivalente de regreso. `pct_vacio` es ese vacío sobre el total del tramo.
    """
    n = net.copy()
    n["mayor"] = np.maximum(n["ab"], n["ba"])
    n["menor"] = np.minimum(n["ab"], n["ba"])
    n["vacio"] = n["mayor"] - n["menor"]
    n["vacio_dia"] = n["vacio"] / dias
    n["pct_vacio"] = np.where(n["total"] > 0, 100.0 * n["vacio"] / n["total"], np.nan)
    n["vacio_km"] = n["vacio"] * n["km"]      # camiones-km vacíos por año en el tramo
    return n


def summary(net: gpd.GeoDataFrame) -> dict:
    """Totales de la red: camiones-km cargados y vacíos por año, y la fracción vacía."""
    n = link_imbalance(net) if "vacio" not in net.columns else net
    total_km = float((n["total"] * n["km"]).sum())
    vacio_km = float(n["vacio_km"].sum())
    return {"camiones_km_total": total_km, "camiones_km_vacios": vacio_km, "pct_vacio": 100.0 * vacio_km / total_km if total_km else float("nan"),
            "tramos": int(len(n)), "km_red": float(n["km"].sum())}


def by_route(net: gpd.GeoDataFrame, top: int = 15) -> pd.DataFrame:
    """Las rutas con más camiones-km vacíos por año."""
    n = link_imbalance(net) if "vacio" not in net.columns else net
    g = n.groupby("etiqueta").agg(km=("km", "sum"), camiones_km=("total", lambda s: float((s * n.loc[s.index, "km"]).sum())),
                                  vacio_km=("vacio_km", "sum")).reset_index()
    g["pct_vacio"] = 100.0 * g["vacio_km"] / g["camiones_km"].where(g["camiones_km"] > 0)
    return g.sort_values("vacio_km", ascending=False).head(top).reset_index(drop=True)


def all_groups(raw: Path = DATA_RAW) -> pd.DataFrame:
    """Vacío estructural de la red por grupo de producto, para ver cuál vuelve más vacío."""
    rows = []
    for g in GRUPOS:
        try:
            s = summary(load_network(g, raw))
        except Exception:
            continue
        rows.append({"grupo": g, **s})
    return pd.DataFrame(rows).sort_values("camiones_km_vacios", ascending=False).reset_index(drop=True)


__all__ = ["load_network", "link_imbalance", "summary", "by_route", "all_groups"]
