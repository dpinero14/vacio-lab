"""Figuras del vacío en el tiempo: la serie nacional, las rutas de la arena y el mapa animado 2012 a 2026."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .maps import BG, ESCALA, INK, MUTED, RULE, color_pct

ACENTO, CONTEXTO, AZUL = "#f2b134", "#6b8799", "#3b8ed0"
REALES = (2012, 2014, 2016, 2018)   # años con matriz publicada; el resto es escenario con drivers


def _style(ax):
    ax.set_facecolor(BG)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(colors=MUTED, labelsize=9.5, length=0)
    ax.grid(axis="y", color=RULE, linewidth=0.8, zorder=0)


def national_series(tramos: pd.DataFrame) -> pd.DataFrame:
    """Por año: camiones-km totales y vacíos (miles de millones), fracción vacía, y si el año es medido o escenario."""
    g = tramos.groupby("anio").apply(lambda d: pd.Series({"camiones_km": (d["total"] * d["km"]).sum() / 1e9, "vacios_km": d["vacio_km"].sum() / 1e9,
                                                          "arena_km": (d["total_arena"] * d["km"]).sum() / 1e9}))
    g["pct_vacio"] = 100.0 * g["vacios_km"] / g["camiones_km"]
    g["medido"] = g.index.isin(REALES)
    return g


def route_series(tramos: pd.DataFrame, rutas: tuple[str, ...]) -> pd.DataFrame:
    """Fracción vacía por ruta y año, ponderada por km."""
    t = tramos[tramos["etiqueta"].isin(rutas)]
    g = t.groupby(["anio", "etiqueta"]).apply(lambda d: 100.0 * d["vacio_km"].sum() / max(1.0, (d["total"] * d["km"]).sum())).rename("pct").reset_index()
    return g.pivot(index="anio", columns="etiqueta", values="pct")


def series_figure(tramos: pd.DataFrame, path: str | Path, rutas: tuple[str, ...] = ("RN 152", "RN 5", "RN 151", "RN 35", "RN 33", "RN 3")) -> Path:
    """Dos paneles: la red nacional (camiones-km y vacío) y las rutas elegidas (fracción vacía), 2012 a 2026."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    nat = national_series(tramos)
    rt = route_series(tramos, rutas)
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12, 5.2), dpi=200)
    fig.patch.set_facecolor(BG)
    fig.subplots_adjust(left=0.06, right=0.98, top=0.78, bottom=0.14, wspace=0.28)
    # panel 1: barras de camiones-km, con la parte vacía en ámbar; medidos con borde, escenarios sin borde
    _style(a1)
    x = nat.index.values
    a1.bar(x, nat["camiones_km"], color=CONTEXTO, width=0.7, zorder=3, alpha=0.9)
    a1.bar(x, nat["vacios_km"], color=ACENTO, width=0.7, zorder=4)
    for xi, m in zip(x, nat["medido"]):
        if m:
            a1.plot([xi - 0.35, xi + 0.35], [-0.12, -0.12], color=INK, linewidth=2.2, solid_capstyle="butt", clip_on=False)
    for xi, v, p in zip(x, nat["camiones_km"], nat["pct_vacio"]):
        a1.text(xi, v + 0.12, f"{p:.0f} %", ha="center", va="bottom", color=INK, fontsize=8.5)
    a1.set_xticks(x); a1.set_xticklabels([str(v) for v in x], rotation=45, fontsize=8.5, ha="right")
    a1.set_ylabel("miles de millones de camiones-km por año", color=MUTED, fontsize=9)
    a1.set_title("La red nacional: lo que circula y lo que vuelve vacío", color=INK, fontsize=11, loc="left", pad=8)
    # panel 2: líneas por ruta, la RN 152 en ámbar
    _style(a2)
    colores = {r: CONTEXTO for r in rutas}; colores["RN 152"] = ACENTO; colores["RN 5"] = AZUL
    presentes = [r for r in rutas if r in rt.columns]
    for r in presentes:
        a2.plot(rt.index, rt[r], color=colores[r], linewidth=2.4 if r in ("RN 152", "RN 5") else 1.4, marker="o", markersize=3.5, zorder=3)
    # etiquetas al final de cada línea, separadas al menos 4 puntos para que no se pisen
    finales = sorted(((float(rt[r].iloc[-1]), r) for r in presentes), key=lambda t: t[0])
    ys = []
    for v, r in finales:
        y = v if not ys else max(v, ys[-1] + 4.0)
        ys.append(y)
        a2.text(rt.index[-1] + 0.15, y, r, color=colores[r], fontsize=9, va="center")
    a2.axvspan(2018.5, 2026.5, color="#ffffff", alpha=0.04, zorder=0)
    a2.set_ylim(0, 100); a2.set_xlim(rt.index.min() - 0.3, rt.index.max() + 1.6)
    a2.set_ylabel("camiones sin carga de vuelta, % del tramo", color=MUTED, fontsize=9)
    a2.set_title("Las rutas de la arena y las del grano", color=INK, fontsize=11, loc="left", pad=8)
    fig.text(0.06, 0.93, "El vacío en el tiempo, 2012 a 2026", color=INK, fontsize=16, fontweight="bold")
    fig.text(0.06, 0.875, "Matrices publicadas en 2012, 2014, 2016 y 2018 (marcadas abajo); de 2019 en adelante, la matriz de 2018 escalada con producción, ventas y arena.",
             color=MUTED, fontsize=9.5)
    fig.text(0.06, 0.03, "Fuente: vacio-lab sobre Secretaría de Transporte, MAGyP, INDEC, Secretaría de Energía y registro de fractura. Asignación propia a la red, validada contra la oficial de 2018.",
             color=MUTED, fontsize=8)
    fig.savefig(path, facecolor=BG)
    plt.close(fig)
    return Path(path)


def animated_map(tramos: pd.DataFrame, net: pd.DataFrame, path: str | Path, anios: tuple[int, ...] | None = None, min_total: float = 5000.0, fps: float = 1.0) -> Path:
    """GIF del mapa año por año: cada tramo con el color de su vacío y el grosor de su tránsito."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    from PIL import Image

    anios = anios or tuple(sorted(tramos["anio"].unique()))
    geom = net.set_index("id")["geometry"]
    tmax = float(tramos["total"].max())
    frames = []
    for a in anios:
        d = tramos[(tramos["anio"] == a) & (tramos["total"] >= min_total)].sort_values("total")
        fig, ax = plt.subplots(figsize=(6.4, 8.4), dpi=110)
        fig.patch.set_facecolor(BG); ax.set_facecolor(BG)
        for _, r in d.iterrows():
            g = geom.get(r["id"])
            if g is None:
                continue
            parts = list(g.geoms) if hasattr(g, "geoms") else [g]
            for p in parts:
                xx, yy = p.xy
                ax.plot(xx, yy, color=color_pct(r["pct_vacio"]), linewidth=0.4 + 2.4 * np.sqrt(r["total"] / tmax), solid_capstyle="round", alpha=0.9)
        ax.set_xlim(-74, -53); ax.set_ylim(-55.5, -21.5); ax.set_aspect(1.25); ax.axis("off")
        medido = a in REALES
        fig.text(0.06, 0.94, f"{a}", color=ACENTO, fontsize=30, fontweight="bold")
        fig.text(0.06, 0.905, "matriz publicada" if medido else "escenario: matriz de 2018 escalada con drivers", color=MUTED, fontsize=9.5)
        tot = (d["total"] * d["km"]).sum() / 1e9; vac = d["vacio_km"].sum() / 1e9
        fig.text(0.06, 0.875, f"{tot:.1f} mil millones de camiones-km · {100 * vac / tot:.0f} % sin carga de vuelta".replace(".", ","), color=INK, fontsize=10)
        handles = [Line2D([0], [0], color=c, lw=4) for _, c in ESCALA]
        ax.legend(handles, [f"{u} % o más" for u, _ in ESCALA], loc="upper right", frameon=False, labelcolor=INK, fontsize=8, title="sin carga de vuelta", title_fontsize=8)
        plt.setp(ax.get_legend().get_title(), color=MUTED)
        fig.text(0.06, 0.02, "vacio-lab · Secretaría de Transporte, matriz origen-destino y red 2018 · asignación propia", color=MUTED, fontsize=7)
        fig.canvas.draw()
        frames.append(Image.fromarray(np.asarray(fig.canvas.buffer_rgba())[:, :, :3]))
        plt.close(fig)
    path = Path(path)
    frames[0].save(path, save_all=True, append_images=frames[1:], duration=int(1000 / fps), loop=0, optimize=True)
    return path


__all__ = ["REALES", "national_series", "route_series", "series_figure", "animated_map"]
