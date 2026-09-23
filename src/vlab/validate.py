"""La asignación contra los conteos de Vialidad: cuántos camiones pone el modelo en cada tramo y cuántos vehículos cuenta la ruta.

Vialidad Nacional publica el tránsito medio diario anual (TMDA) por tramo de
ruta nacional, todos los vehículos en los dos sentidos. La asignación oficial
de 2018 (y la propia de otros años) pone camiones por año por tramo. El
cociente entre los dos es la cuota de pesados implícita: un valor típico en
rutas de carga está entre 10 y 60 %; más de 100 % es imposible y marca un
tramo donde el modelo o el conteo fallan. Cada tramo de la red se aparea con
el segmento de TMDA de su misma ruta más cercano a su punto medio.
"""

from __future__ import annotations

import re
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

from . import CRS_GEO, CRS_METRIC, DATA_RAW

MAX_DIST_M = 3000.0
CUOTAS_REF = (0.10, 0.30, 0.60)


def route_label(code: str) -> str:
    """'0152' -> 'RN 152'; 'A001' -> 'AU 1'; '1V11' -> 'RN 1V11': la etiqueta como la usa la red."""
    c = str(code).strip().upper()
    if c.isdigit():
        return f"RN {int(c)}"
    if re.fullmatch(r"A\d{3}", c):
        return f"AU {int(c[1:])}"
    return f"RN {c.lstrip('0')}"


def load_tmda(anio: int = 2017, raw: Path = DATA_RAW, simplify_m: float = 50.0) -> gpd.GeoDataFrame:
    """Los tramos de TMDA de un año en metros: etiqueta, tmda, descripcio, geometry. Los valores no numéricos ('Urbano') quedan NaN."""
    if anio == 2017:
        g = gpd.read_file(raw / "tmda_2017.geojson")
        g = g.rename(columns={"cod_ruta": "cod", "tmda17": "tmda"})
        g["descripcio"] = g.get("descripcio", pd.Series([""] * len(g)))
    elif anio == 2016:
        g = gpd.read_file(raw / "tmda_2016.geojson")
        g = g.rename(columns={"ruta": "cod", "tmda2016": "tmda"})
    else:
        raise ValueError("hay TMDA para 2016 y 2017")
    g = g[g.geometry.notna() & ~g.geometry.is_empty].copy()       # la capa de 2016 trae tramos sin geometría
    g = g.set_crs(CRS_GEO, allow_override=True).to_crs(CRS_METRIC)
    g["tmda"] = pd.to_numeric(g["tmda"], errors="coerce")
    g["etiqueta"] = g["cod"].map(route_label)
    g["geometry"] = g.geometry.simplify(simplify_m)
    g["anio_tmda"] = anio
    return gpd.GeoDataFrame(g[["etiqueta", "cod", "tmda", "descripcio", "anio_tmda", "geometry"]], geometry="geometry", crs=CRS_METRIC)


def _midpoints(net: gpd.GeoDataFrame) -> gpd.GeoSeries:
    """El punto medio de cada tramo, en metros."""
    from shapely.ops import linemerge

    g = net.to_crs(CRS_METRIC).geometry
    pts = []
    for geom in g:
        line = linemerge(geom) if geom.geom_type == "MultiLineString" else geom
        if line.geom_type == "MultiLineString":          # no se pudo unir: el pedazo más largo
            line = max(line.geoms, key=lambda p: p.length)
        pts.append(line.interpolate(0.5, normalized=True))
    return gpd.GeoSeries(pts, index=net.index, crs=CRS_METRIC)


def match_links(net: gpd.GeoDataFrame, tmda: gpd.GeoDataFrame, max_dist_m: float = MAX_DIST_M) -> pd.DataFrame:
    """Cada tramo de la red con el segmento de TMDA de su misma ruta más cercano a su punto medio: id, etiqueta, tmda, dist_m, descripcio.

    Solo aparean los tramos cuya etiqueta existe en la capa de TMDA (rutas nacionales y autopistas);
    los que quedan a más de `max_dist_m` se descartan.
    """
    mids = _midpoints(net)
    por_ruta = {r: t for r, t in tmda[tmda["tmda"].notna()].groupby("etiqueta")}
    rows = []
    for (i, r), p in zip(net[["id", "etiqueta"]].itertuples(index=False), mids):
        seg = por_ruta.get(r)
        if seg is None or p is None:
            continue
        d = seg.geometry.distance(p).dropna()
        if d.empty:
            continue
        j = d.idxmin()
        if d[j] <= max_dist_m:
            rows.append({"id": i, "etiqueta": r, "tmda": float(seg.loc[j, "tmda"]), "dist_m": float(d[j]), "descripcio": str(seg.loc[j, "descripcio"])})
    return pd.DataFrame(rows, columns=["id", "etiqueta", "tmda", "dist_m", "descripcio"])


def heavy_share(matched: pd.DataFrame, flows: pd.DataFrame, comparacion: str = "oficial 2018 vs TMDA 2017", dias: int = 365) -> pd.DataFrame:
    """Por tramo apareado: camiones por día del modelo (ida más vuelta sobre `dias`), TMDA y la cuota de pesados implícita; `imposible` si supera el TMDA."""
    f = flows[["id", "ab", "ba"]].copy()
    f["camiones_dia"] = (f["ab"] + f["ba"]) / dias
    m = matched.merge(f[["id", "camiones_dia"]], on="id", how="inner")
    m = m[m["tmda"] > 0].copy()
    m["cuota_pesados"] = m["camiones_dia"] / m["tmda"]
    m["imposible"] = m["camiones_dia"] > m["tmda"]
    m["comparacion"] = comparacion
    return m


def by_route(links: pd.DataFrame, min_links: int = 3) -> pd.DataFrame:
    """Por ruta y comparación: mediana y rango intercuartil de la cuota de pesados, correlación de Spearman camiones-TMDA, tramos y tramos imposibles."""
    from scipy.stats import spearmanr

    rows = []
    for (comp, ruta), d in links.groupby(["comparacion", "etiqueta"]):
        con = d[d["camiones_dia"] > 0]
        if len(con) < min_links:
            continue
        rho = float(spearmanr(con["camiones_dia"], con["tmda"]).statistic) if len(con) >= 3 and con["tmda"].nunique() > 1 and con["camiones_dia"].nunique() > 1 else float("nan")
        rows.append({"comparacion": comp, "etiqueta": ruta, "n_tramos": int(len(d)), "n_con_flujo": int(len(con)),
                     "cuota_mediana": float(con["cuota_pesados"].median()), "cuota_q25": float(con["cuota_pesados"].quantile(0.25)),
                     "cuota_q75": float(con["cuota_pesados"].quantile(0.75)), "spearman": rho, "n_imposibles": int(d["imposible"].sum())})
    return pd.DataFrame(rows, columns=["comparacion", "etiqueta", "n_tramos", "n_con_flujo", "cuota_mediana", "cuota_q25", "cuota_q75", "spearman", "n_imposibles"]) \
        .sort_values(["comparacion", "n_tramos"], ascending=[True, False]).reset_index(drop=True)


def overall(links: pd.DataFrame) -> dict:
    """Resumen de una comparación: tramos apareados, mediana y cuartiles de la cuota, Spearman global, tramos imposibles."""
    from scipy.stats import spearmanr

    con = links[links["camiones_dia"] > 0]
    return {"tramos": int(len(links)), "con_flujo": int(len(con)), "cuota_mediana": float(con["cuota_pesados"].median()) if len(con) else float("nan"),
            "cuota_q25": float(con["cuota_pesados"].quantile(0.25)) if len(con) else float("nan"), "cuota_q75": float(con["cuota_pesados"].quantile(0.75)) if len(con) else float("nan"),
            "spearman": float(spearmanr(con["camiones_dia"], con["tmda"]).statistic) if len(con) >= 3 else float("nan"), "imposibles": int(links["imposible"].sum())}


def validation_figure(links: pd.DataFrame, path: str | Path, rutas: tuple[str, ...] = ("RN 152", "RN 9", "RN 33", "RN 3", "RN 7", "RN 12", "RN 14", "RN 34"),
                      comparacion: str | None = None) -> Path:
    """Dispersión log-log de camiones por día contra TMDA por tramo, con las cuotas de referencia y las rutas principales marcadas."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    from .figures import ACENTO, CONTEXTO
    from .maps import BG, INK, MUTED, RULE

    d = links if comparacion is None else links[links["comparacion"] == comparacion]
    d = d[(d["camiones_dia"] > 0) & (d["tmda"] > 0)]
    fig, ax = plt.subplots(figsize=(9.6, 6.6), dpi=200)
    fig.patch.set_facecolor(BG); ax.set_facecolor(BG)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(colors=MUTED, labelsize=9, length=0)
    ax.grid(color=RULE, linewidth=0.7, zorder=0)
    ax.set_xscale("log"); ax.set_yscale("log")
    xmin, xmax = max(50.0, d["tmda"].min() * 0.8), d["tmda"].max() * 1.3
    x = np.array([xmin, xmax])
    for q in CUOTAS_REF:
        ax.plot(x, q * x, color=RULE, linewidth=1.0, linestyle="--", zorder=1)
        ax.text(xmax, q * xmax, f" {int(q * 100)} % pesados", color=MUTED, fontsize=8, va="center")
    ax.plot(x, x, color="#d7301f", linewidth=1.0, linestyle=":", zorder=1)
    ax.text(xmax, xmax, " 100 %: imposible", color="#d7301f", fontsize=8, va="center")
    otros = d[~d["etiqueta"].isin(rutas)]
    ax.scatter(otros["tmda"], otros["camiones_dia"], s=10, color=CONTEXTO, alpha=0.45, linewidths=0, zorder=2)
    imp = d[d["imposible"]]
    ax.scatter(imp["tmda"], imp["camiones_dia"], s=18, facecolors="none", edgecolors="#d7301f", linewidths=0.8, zorder=4)
    puntos = []
    for r in rutas:
        dr = d[d["etiqueta"] == r]
        if dr.empty:
            continue
        c = ACENTO if r == "RN 152" else INK
        ax.scatter(dr["tmda"], dr["camiones_dia"], s=16, color=c, alpha=0.9, linewidths=0, zorder=3)
        puntos.append((float(dr["tmda"].median()), float(dr["camiones_dia"].median()), r, c))
    # cada ruta se etiqueta en la mediana de sus tramos; las etiquetas van en una columna a la derecha,
    # ordenadas por altura y separadas para que no se pisen, con una línea fina hasta su punto
    puntos.sort(key=lambda t: t[1])
    x_lab = xmax * 1.6
    y_prev = None
    for x, y, r, c in puntos:
        y_lab = y if y_prev is None else max(y, y_prev * 1.7)
        ax.annotate(r, (x, y), xytext=(x_lab, y_lab), color=c, fontsize=8.5, fontweight="bold", va="center", ha="left",
                    arrowprops={"arrowstyle": "-", "color": c, "lw": 0.6, "alpha": 0.6}, zorder=5)
        y_prev = y_lab
    ax.set_xlim(xmin, xmax * 3.2)
    ax.set_xlabel("TMDA de Vialidad, vehículos por día en los dos sentidos", color=MUTED, fontsize=9.5)
    ax.set_ylabel("camiones por día asignados al tramo, ida más vuelta", color=MUTED, fontsize=9.5)
    titulo = comparacion or (str(d["comparacion"].iloc[0]) if len(d) else "")
    fig.text(0.07, 0.95, "La asignación contra el conteo de Vialidad", color=INK, fontsize=15, fontweight="bold")
    fig.text(0.07, 0.905, f"Cada punto es un tramo de ruta nacional ({titulo}). Las líneas marcan la cuota de pesados implícita.", color=MUTED, fontsize=8.8)
    fig.text(0.07, 0.875, "En rojo, tramos con más camiones asignados que vehículos contados. Cada ruta, etiquetada en la mediana de sus tramos.", color=MUTED, fontsize=8.8)
    fig.text(0.07, 0.02, "Fuente: vacio-lab sobre Vialidad Nacional (TMDA por tramo, vía IDE Transporte) y Secretaría de Transporte (asignación a la red).",
             color=MUTED, fontsize=7)
    fig.subplots_adjust(left=0.09, right=0.97, top=0.84, bottom=0.11)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, facecolor=BG)
    plt.close(fig)
    return path


def count_stations(rutas: tuple[str, ...] = ("RN 152", "RN 9", "RN 33", "RN 3"), raw: Path = DATA_RAW) -> pd.DataFrame:
    """Las estaciones de conteo de Vialidad de 2019 sobre las rutas pedidas: id_conteo, etiqueta, progresiva, descripcio, distrito, lon, lat."""
    g = gpd.read_file(raw / "conteo_transito_dnv_2019.geojson").set_crs(CRS_GEO, allow_override=True)
    g["etiqueta"] = g["cod_ruta"].map(route_label)
    g = g[g["etiqueta"].isin(rutas)].copy()
    puntos = g.geometry.representative_point()             # la capa trae MultiPoint de un solo punto
    g["lon"], g["lat"] = puntos.x, puntos.y
    g["progresiva"] = pd.to_numeric(g["progresiva"], errors="coerce")
    cols = ["id_conteo", "etiqueta", "cod_ruta", "progresiva", "descripcio", "distrito", "lon", "lat"]
    return pd.DataFrame(g[[c for c in cols if c in g.columns]]).sort_values(["etiqueta", "progresiva"]).reset_index(drop=True)


__all__ = ["MAX_DIST_M", "CUOTAS_REF", "route_label", "load_tmda", "match_links", "heavy_share", "by_route", "overall", "validation_figure", "count_stations"]
