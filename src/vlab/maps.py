"""Figuras y mapa del vacío: los tramos de la red pintados por la fracción de camiones que no tiene carga de vuelta."""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

from .network import link_imbalance

BG, INK, MUTED, RULE = "#0e1b25", "#e9eff3", "#8ea2af", "#22384a"
# del equilibrio al vacío: verde, amarillo, naranja, rojo; una sola escala para el mapa y la figura
ESCALA = [(0, "#4caf50"), (30, "#fee08b"), (55, "#fc8d59"), (80, "#d7301f")]


def color_pct(pct: float) -> str:
    if pct is None or np.isnan(pct):
        return "#556570"
    out = ESCALA[0][1]
    for umbral, color in ESCALA:
        if pct >= umbral:
            out = color
    return out


def empty_map(net: gpd.GeoDataFrame, path: str | Path, zonas: pd.DataFrame | None = None, min_total: float = 5000.0) -> Path:
    """Mapa interactivo: cada tramo con color por vacío, grosor por tránsito y su ficha al pasar el mouse."""
    import folium

    n = link_imbalance(net) if "vacio" not in net.columns else net
    n = n[n["total"] >= min_total].copy()
    # fondo oscuro sin clave de API: el lienzo gris de Esri (los de Carto pasaron a pedir clave en 2026)
    m = folium.Map(location=[-37.5, -64.5], zoom_start=5, tiles=None, control_scale=True)
    folium.TileLayer(tiles="https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}",
                     attr="Tiles &copy; Esri, HERE, Garmin, OpenStreetMap contributors", name="fondo", max_zoom=16, control=False).add_to(m)
    tmax = float(n["total"].max())
    for _, r in n.iterrows():
        w = 1.5 + 6.5 * np.sqrt(r["total"] / tmax)
        tip = (f"<b>{r['etiqueta']}</b> · {r['provincia']}<br>{r['km']:.0f} km · estado {r['estado']}<br>"
               f"ida {r['mayor']:,.0f} · vuelta {r['menor']:,.0f} camiones/año<br><b>{r['pct_vacio']:.0f} % sin carga de vuelta</b> · {r['vacio_dia']:,.0f} camiones vacíos por día").replace(",", ".")
        folium.GeoJson(r["geometry"].__geo_interface__, style_function=lambda f, c=color_pct(r["pct_vacio"]), w=w: {"color": c, "weight": w, "opacity": 0.85},
                       tooltip=folium.Tooltip(tip)).add_to(m)
    if zonas is not None:
        for _, z in zonas.iterrows():
            folium.CircleMarker([z["lat"], z["lon"]], radius=2, color="#c9d5dd", fill=True, fill_opacity=0.9, weight=0, tooltip=f"{z['centroide'].title()} ({z['codigo']})").add_to(m)
    leyenda = ("<div style='position:fixed;bottom:24px;left:24px;z-index:9999;background:#0e1b25;color:#e9eff3;padding:12px 14px;border:1px solid #22384a;font:13px Segoe UI,sans-serif'>"
               "<b>Camiones sin carga de vuelta, 2018</b><br>por tramo, sobre el total del tramo<br>"
               + "".join(f"<span style='display:inline-block;width:14px;height:8px;background:{c};margin-right:6px'></span>{u} % o más<br>" for u, c in ESCALA)
               + "<span style='color:#8ea2af'>grosor: camiones por año · fuente: Secretaría de Transporte, MOD 2018</span></div>")
    m.get_root().html.add_child(folium.Element(leyenda))
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    m.save(str(path))
    return path


def empty_figure(net: gpd.GeoDataFrame, path: str | Path, titulo: str = "El mapa del vacío", min_total: float = 5000.0) -> Path:
    """Figura estática del país con los tramos por vacío, para el README y el post."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D

    n = link_imbalance(net) if "vacio" not in net.columns else net
    n = n[n["total"] >= min_total].copy().sort_values("total")
    fig, ax = plt.subplots(figsize=(7.2, 9.6), dpi=200)
    fig.patch.set_facecolor(BG); ax.set_facecolor(BG)
    tmax = float(n["total"].max())
    for _, r in n.iterrows():
        n_geom = r["geometry"]
        parts = list(n_geom.geoms) if hasattr(n_geom, "geoms") else [n_geom]
        for p in parts:
            x, y = p.xy
            ax.plot(x, y, color=color_pct(r["pct_vacio"]), linewidth=0.4 + 2.6 * np.sqrt(r["total"] / tmax), solid_capstyle="round", alpha=0.9)
    ax.set_xlim(-74, -53); ax.set_ylim(-55.5, -21.5); ax.set_aspect(1.25); ax.axis("off")
    fig.text(0.05, 0.955, titulo, color=INK, fontsize=16, fontweight="bold")
    fig.text(0.05, 0.925, "Camiones que cruzan cada tramo sin carga de vuelta, sobre el total del tramo. Grosor: camiones por año.", color=MUTED, fontsize=9.5)
    handles = [Line2D([0], [0], color=c, lw=4) for _, c in ESCALA]
    ax.legend(handles, [f"{u} % o más" for u, _ in ESCALA], loc="upper right", frameon=False, labelcolor=INK, fontsize=9, title="sin carga de vuelta", title_fontsize=9)
    plt.setp(ax.get_legend().get_title(), color=MUTED)
    fig.text(0.05, 0.02, "Fuente: Secretaría de Transporte, Matriz Origen-Destino vial 2018, red simplificada con asignación de camiones por sentido. vacio-lab.", color=MUTED, fontsize=7.5)
    fig.savefig(path, facecolor=BG, bbox_inches="tight")
    plt.close(fig)
    return Path(path)


__all__ = ["color_pct", "empty_map", "empty_figure", "ESCALA"]
