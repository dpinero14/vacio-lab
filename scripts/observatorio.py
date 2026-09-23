"""El observatorio del vacío: cada año con lo que se mide y lo que se supone, asignado a la red y validado contra los conteos de Vialidad.

Para cada año pedido arma la matriz de camiones: la publicada si existe (2012,
2014, 2016 y 2018), o la de 2018 graduada producto por producto, con las fuentes
que miden por zona (SENASA, estaciones de servicio, AFCP, MAGyP) donde las hay y
el driver nacional donde no. La asigna a la red por caminos mínimos, suma la
arena de fractura del registro, y escribe en data/processed:

- observatorio_tramos.csv: camiones por tramo, sentido y año, con el vacío;
- observatorio_estado.csv: por año y producto, si es medido, escenario o plano, y con qué fuente;
- observatorio_resumen.csv: por año, camiones-km, vacíos, fracción y cuántos productos hay de cada clase;
- validacion_tmda.csv, estaciones_conteo_2019.csv y docs/figures/validacion_tmda.png: la asignación contra el TMDA.

Uso: python scripts/observatorio.py --anios 2012-2026   (o una lista: --anios 2018,2022,2025)
"""

import argparse
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from vlab import ANIOS, DATA_PROC, FIGURES  # noqa: E402
from vlab.assign import assign, build_graph, sum_matrices, zone_nodes  # noqa: E402
from vlab.drivers import driver_table, sand_by_year  # noqa: E402
from vlab.graduate import ARENA_KEY, graduate, published_state, summarize_state  # noqa: E402
from vlab.network import load_network  # noqa: E402
from vlab.od import all_products, zones  # noqa: E402
from vlab.projection import ARENA_DESTINO, T_POR_CAMION, link_empties_by_year, sand_trucks  # noqa: E402
from vlab.sources import available, measured_tables  # noqa: E402
from vlab.validate import by_route, count_stations, heavy_share, load_tmda, match_links, overall, validation_figure  # noqa: E402


def parse_years(texto: str) -> tuple[int, ...]:
    """'2012-2026' o '2018,2022,2025' a una tupla de años."""
    out = []
    for parte in texto.split(","):
        parte = parte.strip()
        if "-" in parte:
            a, b = parte.split("-")
            out += list(range(int(a), int(b) + 1))
        elif parte:
            out.append(int(parte))
    return tuple(sorted(set(out)))


def sand_already(matrices: dict) -> float:
    """Camiones de arena silícea que la matriz de un año ya manda al destino de la arena, en toneladas."""
    return sum(float(m[ARENA_DESTINO].sum()) for (g, p), m in matrices.items() if p == "arena silicea") * T_POR_CAMION


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--anios", default="2012-2026", help="rango '2012-2026' o lista '2018,2022,2025'")
    ap.add_argument("--sin-validacion", action="store_true", help="no correr la comparación con el TMDA")
    args = ap.parse_args()
    anios = parse_years(args.anios)
    t0 = time.time()
    DATA_PROC.mkdir(parents=True, exist_ok=True)

    z = zones(); codes = list(z["codigo"])
    net = load_network()
    G, links = build_graph(net); nodos = zone_nodes(G, z)
    print(f"red: {len(net)} tramos, grafo de {G.number_of_nodes()} nodos; {len(codes)} zonas")

    drivers = driver_table(); arena = sand_by_year()
    Mc18 = all_products(2018, codes, "camiones")
    print(f"matriz 2018: {len(Mc18)} productos en camiones; drivers {int(drivers.index.min())}-{int(drivers.index.max())}")

    registry = available()
    print("fuentes medidas por zona:")
    for p, r in registry.items():
        print(f"  {p:10s} {r['lado']:8s} {r['anios'][0]}-{r['anios'][1]}  {r['fuente']}")
    # la tabla medida se arma para todos los años con fuente, no solo los pedidos: un producto sin 2018 medido
    # (el cemento, que la AFCP publica desde 2021) se encadena desde su primer año medido
    anios_medidos = sorted({2018} | set(anios) | {a for r in registry.values() for a in r["lista"] if a >= 2012})
    medidas = measured_tables(tuple(anios_medidos), zonas=z, registry=registry)
    print(f"tabla medida: {len(medidas)} filas, {medidas['producto'].nunique() if len(medidas) else 0} productos, años {sorted(medidas['anio'].unique().tolist()) if len(medidas) else []}")

    filas, estados, asig_2016 = [], [], None
    for a in anios:
        ta = time.time()
        arena_t = float(arena.get(a, 0.0))
        if a in ANIOS:
            Mc = Mc18 if a == 2018 else all_products(a, codes, "camiones")
            ya = sand_already(Mc)
            estado = published_state(Mc, a, arena=arena_t > ya)
            arena_m = sand_trucks(arena_t, ya, zone_codes=codes)
            total = sum_matrices(Mc)
            fuente = "matriz publicada"
        else:
            if a not in drivers.index:
                print(f"  {a}: sin drivers, se saltea")
                continue
            # se gradúa la edición en camiones, que es la que va a la red; las hojas se llaman distinto que en toneladas
            # ('bovinos en pie', 'trit. petreos camion') y graduate las reconoce por su nombre canónico. El factor nacional
            # del estado es el cociente de camiones del año sobre 2018.
            Mc, estado = graduate(Mc18, a, medidas, drivers, arena_t=arena_t, unidad="camiones")
            arena_m = Mc.pop(ARENA_KEY, sand_trucks(0.0, zone_codes=codes))
            total = sum_matrices(Mc)
            fuente = "graduada"
        asig = assign(G, links, nodos, total.add(arena_m, fill_value=0.0))
        asig_arena = assign(G, links, nodos, arena_m).rename(columns={"ab": "ab_arena", "ba": "ba_arena", "total": "total_arena"})
        filas.append(asig.merge(asig_arena, on="id").assign(anio=a))
        estados.append(estado)
        if a == 2016:
            asig_2016 = asig
        resumen = summarize_state(estado).loc[a]
        print(f"  {a} ({fuente}): {total.to_numpy().sum() / 1e6:.2f} M camiones + {arena_m.to_numpy().sum() / 1e3:.0f} mil de arena; "
              f"{resumen['n_medidos']} medidos, {resumen['n_escenario']} escenario, {resumen['n_plano']} planos; {time.time() - ta:.0f} s")

    por_anio = pd.concat(filas, ignore_index=True)
    tramos = link_empties_by_year(por_anio, net)
    tramos.to_csv(DATA_PROC / "observatorio_tramos.csv", index=False)
    estado = pd.concat(estados, ignore_index=True)
    estado.to_csv(DATA_PROC / "observatorio_estado.csv", index=False)
    nat = tramos.groupby("anio").apply(lambda d: pd.Series({"camiones_km": (d["total"] * d["km"]).sum() / 1e9, "vacios_km": d["vacio_km"].sum() / 1e9,
                                                            "arena_km": (d["total_arena"] * d["km"]).sum() / 1e9}), include_groups=False)
    nat["pct_vacio"] = 100.0 * nat["vacios_km"] / nat["camiones_km"]
    resumen = nat.join(summarize_state(estado))
    resumen["medido"] = resumen.index.isin(ANIOS)
    resumen = resumen.reset_index()[["anio", "camiones_km", "vacios_km", "arena_km", "pct_vacio", "n_medidos", "n_escenario", "n_plano", "medido"]]
    resumen.to_csv(DATA_PROC / "observatorio_resumen.csv", index=False)
    print("resumen por año:")
    print(resumen.round(2).to_string(index=False))

    if not args.sin_validacion:
        tv = time.time()
        partes = []
        m17 = match_links(net, load_tmda(2017))
        partes.append(heavy_share(m17, net, "oficial 2018 vs TMDA 2017"))
        if asig_2016 is not None:
            m16 = match_links(net, load_tmda(2016))
            partes.append(heavy_share(m16, asig_2016, "propia 2016 vs TMDA 2016"))
        val = pd.concat(partes, ignore_index=True)
        val.to_csv(DATA_PROC / "validacion_tmda.csv", index=False)
        rutas = by_route(val)
        rutas.to_csv(DATA_PROC / "validacion_tmda_rutas.csv", index=False)
        validation_figure(val, FIGURES / "validacion_tmda.png", comparacion="oficial 2018 vs TMDA 2017")
        est = count_stations()
        est.to_csv(DATA_PROC / "estaciones_conteo_2019.csv", index=False)
        for comp, d in val.groupby("comparacion"):
            o = overall(d)
            print(f"validación {comp}: {o['tramos']} tramos apareados, cuota de pesados mediana {100 * o['cuota_mediana']:.0f} % "
                  f"(q25 {100 * o['cuota_q25']:.0f}, q75 {100 * o['cuota_q75']:.0f}), Spearman {o['spearman']:.2f}, {o['imposibles']} imposibles")
        print(f"estaciones de conteo 2019 en las rutas elegidas: {len(est)}; validación en {time.time() - tv:.0f} s")
    print(f"listo en {(time.time() - t0) / 60:.1f} min")


if __name__ == "__main__":
    main()
