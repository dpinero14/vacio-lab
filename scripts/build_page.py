"""Arma la página del observatorio (docs/observatorio.html) con lo que dejó scripts/observatorio.py.

Lee data/processed/observatorio_*.csv y validacion_tmda_rutas.csv, dibuja la serie del
observatorio, copia los CSV a docs/data (que sí se versiona: es el corte publicado) y escribe
una página estática sin dependencias. Corre después del observatorio, a mano o en Actions.
"""

import html
import shutil
import sys
from datetime import date
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from vlab import ANIOS, DATA_PROC, DOCS, FIGURES  # noqa: E402

DOCS_DATA = DOCS / "data"
BG, INK, MUTED, RULE, ACENTO, CONTEXTO, AZUL = "#0e1b25", "#f2f2f2", "#8fa3b0", "#22333f", "#f2b134", "#6b8799", "#26c6da"


def serie_figure(resumen: pd.DataFrame, path: Path) -> Path:
    """Dos paneles: camiones-km totales y vacíos por año (con cuántos productos van medidos), y la fracción vacía."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    r = resumen.sort_values("anio")
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12, 5.0), dpi=200)
    fig.patch.set_facecolor(BG)
    fig.subplots_adjust(left=0.06, right=0.98, top=0.78, bottom=0.16, wspace=0.25)
    for ax in (a1, a2):
        ax.set_facecolor(BG)
        for s in ax.spines.values():
            s.set_visible(False)
        ax.tick_params(colors=MUTED, labelsize=9, length=0)
        ax.grid(axis="y", color=RULE, linewidth=0.8, zorder=0)
    x = r["anio"].to_numpy()
    a1.bar(x, r["camiones_km"], color=CONTEXTO, width=0.7, zorder=3, alpha=0.9)
    a1.bar(x, r["vacios_km"], color=ACENTO, width=0.7, zorder=4)
    for xi, v, n, m in zip(x, r["camiones_km"], r["n_medidos"], r["medido"]):
        a1.text(xi, v + 0.12, "matriz" if m else f"{int(n)} med.", ha="center", va="bottom", color=INK if m else MUTED, fontsize=7.2, rotation=90)
    a1.set_xticks(x)
    a1.set_xticklabels([str(v) for v in x], rotation=45, fontsize=8.5, ha="right")
    a1.set_ylim(0, r["camiones_km"].max() * 1.35)
    a1.set_ylabel("miles de millones de camiones-km por año", color=MUTED, fontsize=9)
    a1.set_title("Lo que circula (gris) y lo que no tiene carga de vuelta (ámbar)", color=INK, fontsize=10.5, loc="left", pad=8)
    a2.plot(x, r["pct_vacio"], color=ACENTO, linewidth=2.4, marker="o", markersize=4, zorder=3)
    med = r[r["medido"]]
    a2.scatter(med["anio"], med["pct_vacio"], s=70, facecolors="none", edgecolors=INK, linewidths=1.4, zorder=4)
    a2.set_ylim(35, 50)
    a2.set_xticks(x)
    a2.set_xticklabels([str(v) for v in x], rotation=45, fontsize=8.5, ha="right")
    a2.set_ylabel("camiones-km sin carga de vuelta, %", color=MUTED, fontsize=9)
    a2.set_title("La fracción vacía; con aro, los años con matriz publicada", color=INK, fontsize=10.5, loc="left", pad=8)
    fig.text(0.06, 0.93, "El observatorio del vacío, año por año", color=INK, fontsize=16, fontweight="bold")
    fig.text(0.06, 0.875, "Matrices publicadas en 2012, 2014, 2016 y 2018. Los demás años: la de 2018 con cada producto medido por zona donde hay fuente ('med.' cuenta esos productos) o escalado con su driver.",
             color=MUTED, fontsize=8.2)
    fig.text(0.06, 0.03, f"Fuente: vacio-lab, corrida del {date.today():%d/%m/%Y}. Secretaría de Transporte, MAGyP, SENASA, Secretaría de Energía, AFCP, INDEC y registro de fractura; asignación propia a la red.",
             color=MUTED, fontsize=7.6)
    fig.savefig(path, facecolor=BG)
    plt.close(fig)
    return path


def _tabla(df: pd.DataFrame, cols: list[tuple[str, str, str]]) -> str:
    """Una tabla HTML: cols = (columna, encabezado, formato)."""
    head = "".join(f"<th>{html.escape(h)}</th>" for _, h, _ in cols)
    filas = []
    for _, row in df.iterrows():
        celdas = []
        for c, _, fmt in cols:
            v = row[c]
            if pd.isna(v):
                s = "–"
            elif fmt == "int":
                s = f"{int(v):,}".replace(",", ".")
            elif fmt.startswith("f"):
                s = f"{float(v):.{fmt[1]}f}".replace(".", ",")
            elif fmt == "bool":
                s = "sí" if bool(v) else "no"
            else:
                s = html.escape(str(v))
            celdas.append(f"<td>{s}</td>")
        filas.append("<tr>" + "".join(celdas) + "</tr>")
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(filas)}</tbody></table>"


def main() -> None:
    resumen = pd.read_csv(DATA_PROC / "observatorio_resumen.csv")
    estado = pd.read_csv(DATA_PROC / "observatorio_estado.csv", encoding="utf-8")
    rutas = pd.read_csv(DATA_PROC / "validacion_tmda_rutas.csv", encoding="utf-8")
    val = pd.read_csv(DATA_PROC / "validacion_tmda.csv", encoding="utf-8")
    FIGURES.mkdir(parents=True, exist_ok=True)
    DOCS_DATA.mkdir(parents=True, exist_ok=True)
    serie_figure(resumen, FIGURES / "observatorio_serie.png")
    for f in ("observatorio_tramos.csv", "observatorio_estado.csv", "observatorio_resumen.csv", "validacion_tmda.csv", "validacion_tmda_rutas.csv", "estaciones_conteo_2019.csv"):
        if (DATA_PROC / f).exists():
            shutil.copy(DATA_PROC / f, DOCS_DATA / f)

    hoy = date.today()
    ultimo_completo = int(resumen.loc[resumen["n_medidos"] >= 10, "anio"].max())
    u = resumen.set_index("anio").loc[ultimo_completo]
    b = resumen.set_index("anio").loc[2018]
    est_u = estado[estado["anio"] == ultimo_completo]
    medidos = est_u[est_u["tipo"].str.startswith("medido")].sort_values(["tipo", "grupo", "producto"])
    escenario = est_u[est_u["tipo"] == "escenario driver"]
    planos = est_u[est_u["tipo"] == "plano"]
    v18 = val[val["comparacion"] == "oficial 2018 vs TMDA 2017"]
    v18 = v18[(v18["tmda"] > 0) & (v18["camiones_dia"] > 0)]
    r18 = rutas[rutas["comparacion"] == "oficial 2018 vs TMDA 2017"].sort_values("n_tramos", ascending=False).head(12)

    def n(v, d=2):
        return f"{v:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")

    resumen_html = _tabla(resumen.assign(fuente=resumen["medido"].map({True: "matriz publicada", False: "2018 graduada"})),
                          [("anio", "año", "s"), ("fuente", "base", "s"), ("camiones_km", "camiones-km (1e9)", "f2"), ("vacios_km", "vacíos (1e9)", "f2"),
                           ("pct_vacio", "% sin vuelta", "f1"), ("n_medidos", "medidos", "int"), ("n_escenario", "escenario", "int"), ("n_plano", "planos", "int")])
    medidos_html = _tabla(medidos, [("grupo", "grupo", "s"), ("producto", "producto", "s"), ("tipo", "cómo", "s"), ("fuente", "fuente", "s"), ("factor_nacional", f"factor {ultimo_completo}/2018", "f2")])
    drivers_html = _tabla(escenario.groupby("fuente").size().rename("productos").reset_index().sort_values("productos", ascending=False),
                          [("fuente", "driver", "s"), ("productos", "productos", "int")])
    rutas_html = _tabla(r18.assign(cuota_mediana=100 * r18["cuota_mediana"], cuota_q25=100 * r18["cuota_q25"], cuota_q75=100 * r18["cuota_q75"]),
                        [("etiqueta", "ruta", "s"), ("n_tramos", "tramos", "int"), ("cuota_mediana", "cuota de pesados mediana, %", "f0"), ("cuota_q25", "q25", "f0"),
                         ("cuota_q75", "q75", "f0"), ("spearman", "Spearman", "f2"), ("n_imposibles", "imposibles", "int")])
    import numpy as np
    from scipy.stats import spearmanr
    rho = spearmanr(v18["tmda"], v18["camiones_dia"]).statistic if len(v18) > 2 else np.nan
    cuota = 100 * v18["cuota_pesados"].median()
    imposibles = int(v18["imposible"].sum())

    page = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Observatorio del vacío</title>
<meta name="description" content="Cuánto del transporte de cargas argentino circula sin carga de vuelta, año por año, con las fuentes abiertas que lo miden.">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;600&family=IBM+Plex+Mono&display=swap">
<style>
:root{{--bg:{BG};--ink:{INK};--muted:{MUTED};--rule:{RULE};--acento:{ACENTO};--azul:{AZUL};--panel:#15242f}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--ink);font-family:"IBM Plex Sans",system-ui,sans-serif;line-height:1.5}}
main{{max-width:980px;margin:0 auto;padding:32px 16px 64px}}
h1{{font-size:2rem;margin:0 0 4px;letter-spacing:-.01em}}
h2{{font-size:1.25rem;margin:40px 0 8px;color:var(--acento)}}
p,li{{max-width:68ch}}
.sub{{color:var(--muted);margin:0 0 24px}}
.kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin:20px 0}}
.kpi{{background:var(--panel);border-radius:8px;padding:14px 16px}}
.kpi b{{display:block;font-size:1.7rem;font-variant-numeric:tabular-nums;color:var(--acento)}}
.kpi span{{color:var(--muted);font-size:.9rem}}
figure{{margin:16px 0}} figure img{{width:100%;height:auto;border-radius:6px}} figcaption{{color:var(--muted);font-size:.85rem}}
.tabla{{overflow-x:auto;margin:12px 0}} table{{border-collapse:collapse;width:100%;font-size:.88rem;font-variant-numeric:tabular-nums}}
th,td{{padding:6px 10px;border-bottom:1px solid var(--rule);text-align:right;white-space:nowrap}} th:first-child,td:first-child,th:nth-child(2),td:nth-child(2){{text-align:left}}
th{{color:var(--muted);font-weight:600}}
a{{color:var(--azul)}} code{{font-family:"IBM Plex Mono",monospace;font-size:.85em;color:var(--acento)}}
.nota{{color:var(--muted);font-size:.9rem}}
footer{{margin-top:48px;color:var(--muted);font-size:.85rem;border-top:1px solid var(--rule);padding-top:16px}}
</style>
</head>
<body>
<main>
<h1>El observatorio del vacío</h1>
<p class="sub">Cuánto del transporte automotor de cargas argentino circula en un sentido sin carga de vuelta, año por año, tramo por tramo. Corrida del {hoy:%d/%m/%Y}.</p>

<div class="kpis">
  <div class="kpi"><b>{n(u['pct_vacio'], 1)} %</b><span>de los camiones-km de {ultimo_completo} sin carga de vuelta ({n(b['pct_vacio'], 1)} % en 2018)</span></div>
  <div class="kpi"><b>{n(u['camiones_km'], 2)}</b><span>miles de millones de camiones-km en {ultimo_completo}</span></div>
  <div class="kpi"><b>{int(u['n_medidos'])}</b><span>productos medidos por zona en {ultimo_completo}; {int(u['n_escenario'])} con driver nacional, {int(u['n_plano'])} sin dato</span></div>
  <div class="kpi"><b>{n(cuota, 0)} %</b><span>cuota de pesados que implica la asignación 2018 contra el conteo de Vialidad (mediana por tramo)</span></div>
</div>

<h2>La serie</h2>
<figure><img src="figures/observatorio_serie.png" alt="Camiones-kilómetro totales y vacíos por año, y la fracción vacía"><figcaption>Los años con matriz publicada llevan aro; el resto es la matriz de 2018 graduada producto por producto.</figcaption></figure>
<div class="tabla">{resumen_html}</div>
<p class="nota">Cómo leer el porcentaje: por cada 100 camiones cargados que cruzan un tramo en un sentido, ese número no tiene un camión cargado que lo cruce en el otro. Si vuelven vacíos por la misma ruta, son 3 de cada 10 kilómetros de camión, comparable con el 21,6 % de vehículo-kilómetros vacíos que mide Eurostat.</p>

<h2>Qué se mide y qué se supone en {ultimo_completo}</h2>
<p>Un producto está <em>medido</em> cuando una fuente abierta dice cuánto se movió en cada zona: el origen (la producción por departamento) o el destino (las ventas o el consumo por localidad o provincia). Con eso, cada zona de la matriz de 2018 se escala por su propio factor, no por uno nacional. Lo que ninguna fuente mide se escala con el driver nacional de su grupo; lo que no tiene driver queda como en 2018 y se declara.</p>
<div class="tabla">{medidos_html}</div>
<p class="nota">Con driver nacional, {len(escenario)} productos:</p>
<div class="tabla">{drivers_html}</div>
<p class="nota">Sin dato, planos como en 2018: {len(planos)} productos, en su mayoría minerales, regionales menores e industrializados sin serie propia.</p>

<h2>La asignación contra el conteo de Vialidad</h2>
<p>Vialidad Nacional cuenta vehículos por tramo (TMDA, todos los vehículos, los dos sentidos). Los camiones que la asignación pone en cada tramo no pueden superar ese conteo, y la cuota que representan tiene que parecerse a la cuota de pesados de una ruta de carga. Sobre {len(v18):,} tramos apareados, la asignación oficial de 2018 implica una cuota de pesados mediana del {n(cuota, 0)} %, con una correlación de rangos de {n(rho, 2)} con el conteo y {imposibles} tramos imposibles (más camiones asignados que vehículos contados).</p>
<figure><img src="figures/validacion_tmda.png" alt="Camiones asignados por tramo contra el TMDA de Vialidad"></figure>
<div class="tabla">{rutas_html}</div>
<p class="nota">Vialidad publica el TMDA sin composición por categoría; la cuota de pesados sale de dividir camiones asignados por vehículos contados y es una verificación de orden de magnitud, no una calibración.</p>

<h2>Descargas</h2>
<ul>
  <li><a href="data/observatorio_tramos.csv">observatorio_tramos.csv</a>: camiones por tramo, sentido y año, con el vacío (id, ab, ba, total, km, etiqueta de ruta, vacío por día y en km).</li>
  <li><a href="data/observatorio_estado.csv">observatorio_estado.csv</a>: por año y producto, si es medido, escenario o plano, con la fuente y el factor.</li>
  <li><a href="data/observatorio_resumen.csv">observatorio_resumen.csv</a>: la serie nacional.</li>
  <li><a href="data/validacion_tmda.csv">validacion_tmda.csv</a> y <a href="data/validacion_tmda_rutas.csv">validacion_tmda_rutas.csv</a>: la comparación con Vialidad por tramo y por ruta.</li>
  <li><a href="data/estaciones_conteo_2019.csv">estaciones_conteo_2019.csv</a>: las estaciones de conteo de Vialidad sobre las rutas de referencia.</li>
</ul>

<h2>Cómo se arma y qué le falta</h2>
<ul>
  <li>Base: las matrices origen-destino de la Secretaría de Transporte (123 zonas, 113 productos) de {', '.join(str(a) for a in ANIOS)}, asignadas a la red simplificada de 1.731 tramos por caminos mínimos.</li>
  <li>Fuentes que miden por zona: producción agrícola por departamento (MAGyP), movimientos de hacienda entre departamentos (SENASA, 2013 a 2018), volúmenes por estación de servicio (Secretaría de Energía), consumo de cemento por provincia (AFCP, desde 2021) y arena bombeada (registro de fractura).</li>
  <li>Pedidos en curso: la matriz 2022 del CESPA, los viajes de granos de la Carta de Porte Electrónica y las encuestas en ruta de la Secretaría (ver <code>PEDIDOS.md</code>).</li>
  <li>Lo que nadie mide: el camión vacío real. El <a href="https://github.com/dpinero14/vacio-lab/tree/main/panel">panel de flotas</a> propone una semana de viajes por vehículo, como la encuesta continua del Reino Unido.</li>
  <li>Se corre solo una vez por mes (GitHub Actions) y cada corrida reemplaza esta página y los CSV.</li>
</ul>

<footer>vacio-lab · <a href="https://github.com/dpinero14/vacio-lab">github.com/dpinero14/vacio-lab</a> · <a href="mapa_vacio.html">el mapa del vacío</a> · datos abiertos del Estado argentino, método abierto.</footer>
</main>
</body>
</html>
"""
    (DOCS / "observatorio.html").write_text(page, encoding="utf-8")
    print(f"página: {DOCS / 'observatorio.html'}; último año completo {ultimo_completo}: {u['pct_vacio']:.1f} % vacío, {int(u['n_medidos'])} medidos")


if __name__ == "__main__":
    main()
