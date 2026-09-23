"""La graduación: cada producto pasa de escenario a medido cuando una fuente abierta lo mide zona por zona.

La proyección escala la matriz de 2018 con un factor nacional por producto.
Acá, cuando existe una fuente que mide el producto por zona, el factor deja
de ser uno solo: cada zona de origen o de destino se escala por lo que la
fuente midió en esa zona respecto de 2018. Si la fuente mide las dos puntas,
la matriz se ajusta a los dos márgenes por ajuste proporcional iterativo
(IPF, el método de Furness). Lo que ninguna fuente mide sigue con su driver
nacional, y lo que no tiene driver queda plano. Todo queda declarado en una
tabla de estado por año y producto, con la fuente y el factor implícito.
"""

from __future__ import annotations

import re

import numpy as np
import pandas as pd

from .projection import ARENA_DESTINO, ARENA_ORIGEN, PRODUCT_DRIVER, T_POR_CAMION, add_sand, sand_trucks, scale_matrices

# los factores por zona se recortan a este rango: una zona con muy poco en 2018 daría cocientes absurdos
CLIP = (0.2, 5.0)
ESTADO_COLS = ["anio", "grupo", "producto", "tipo", "fuente", "factor_nacional"]
ARENA_KEY = ("mineria arena de fractura", "arena de fractura no vista")
# la edición en camiones nombra algunas hojas distinto que la de toneladas: 'bovinos en pie', 'trit. petreos camion', 'alum. elab.'
ALIAS = {"alum. elab.": "aluminio elab.", "arena contr.": "arena const.", "dolomita triturada": "dolomita trit.", "peras y manzanas": "peras y manzana"}
_SUFIJOS = re.compile(r"\s+(en pie|camion|cam\.)$|\s+\.$")


def canonical_product(name: str) -> str:
    """'bovinos en pie' -> 'bovinos', 'trit. petreos camion' -> 'trit. petreos': el nombre como en la edición en toneladas y en los drivers."""
    n = _SUFIJOS.sub("", str(name).strip().lower())
    return ALIAS.get(n, n)


def ipf(m: pd.DataFrame, row_targets: pd.Series | None, col_targets: pd.Series | None, iters: int = 100, tol: float = 1e-6) -> pd.DataFrame:
    """Ajuste proporcional iterativo: escala filas y columnas alternadamente hasta que los márgenes coinciden con los objetivos.

    Cualquiera de los dos objetivos puede ser None. Si los dos totales difieren, se llevan a su media
    geométrica, porque no hay matriz que cumpla los dos. Las filas o columnas que en la matriz suman
    cero no se pueden escalar y quedan en cero, aunque tengan objetivo.
    """
    a = m.to_numpy(dtype=float).copy()
    r = None if row_targets is None else row_targets.reindex(m.index).fillna(0.0).to_numpy(dtype=float)
    c = None if col_targets is None else col_targets.reindex(m.columns).fillna(0.0).to_numpy(dtype=float)
    if r is not None and c is not None and r.sum() > 0 and c.sum() > 0:
        total = float(np.sqrt(r.sum() * c.sum()))
        r, c = r * (total / r.sum()), c * (total / c.sum())
    for _ in range(iters):
        delta = 0.0
        if r is not None:
            rs = a.sum(axis=1)
            f = np.where(rs > 0, r / np.where(rs > 0, rs, 1.0), 1.0)
            a *= f[:, None]
            delta = max(delta, float(np.abs(f[rs > 0] - 1.0).max()) if (rs > 0).any() else 0.0)
        if c is not None:
            cs = a.sum(axis=0)
            f = np.where(cs > 0, c / np.where(cs > 0, cs, 1.0), 1.0)
            a *= f[None, :]
            delta = max(delta, float(np.abs(f[cs > 0] - 1.0).max()) if (cs > 0).any() else 0.0)
        if delta < tol:
            break
    return pd.DataFrame(a, index=m.index, columns=m.columns)


def zone_factors(measured: pd.DataFrame, anio: int, base: int, lado: str, codes: list[str] | None = None, clip: tuple[float, float] | None = CLIP) -> pd.Series:
    """Factor de cada zona entre `base` y `anio` en una tabla medida de un producto: medido(anio) / medido(base), por `lado` ('origen' o 'destino').

    Las zonas que faltan en alguno de los dos años, o con cero en la base, reciben el factor nacional
    (total del año sobre total de la base). Con `codes` la serie se completa a todas las zonas.
    El resultado se recorta a `clip` para que una zona chica no dispare la matriz.
    """
    t = measured.dropna(subset=[lado])
    por = t.groupby([lado, "anio"])["t"].sum().unstack("anio")
    if anio not in por.columns or base not in por.columns:
        raise KeyError(f"la tabla medida no tiene {anio} y {base} del lado {lado}")
    nacional = float(por[anio].sum() / por[base].sum()) if por[base].sum() > 0 else 1.0
    f = por[anio] / por[base].where(por[base] > 0)
    f = f.where(f.notna() & np.isfinite(f), nacional)
    if codes is not None:
        f = f.reindex(codes).fillna(nacional)
    if clip is not None:
        f = f.clip(*clip)
    f.name = f"factor_{lado}_{anio}_vs_{base}"
    f.attrs["nacional"] = nacional
    return f


def _sides(t: pd.DataFrame) -> str:
    """Qué punta mide una tabla: 'ambos', 'origen' o 'destino'."""
    o, d = t["origen"].notna().any(), t["destino"].notna().any()
    return "ambos" if o and d else ("origen" if o else "destino")


def _chain_base(t: pd.DataFrame, anio: int, base: int, drivers: pd.DataFrame | None, driver: str | None) -> tuple[int, float] | None:
    """El año base efectivo de una tabla medida: `base` si está; si no, el primer año medido anterior a `anio`, con el driver nacional para llegar desde `base`."""
    anios = sorted(int(a) for a in t["anio"].unique())
    if base in anios:
        return base, 1.0
    previos = [a for a in anios if base < a < anio]
    if not previos or drivers is None or driver is None or driver not in drivers.columns:
        return None
    b = previos[0]
    if b not in drivers.index or base not in drivers.index or pd.isna(drivers.loc[b, driver]) or pd.isna(drivers.loc[base, driver]) or drivers.loc[base, driver] == 0:
        return None
    return b, float(drivers.loc[b, driver] / drivers.loc[base, driver])


def graduate(matrices_2018: dict[tuple[str, str], pd.DataFrame], anio: int, measured_tables: pd.DataFrame | dict | None, drivers: pd.DataFrame | None,
             base: int = 2018, grupo_de: dict[str, str] | None = None, arena_t: float | None = None, unidad: str = "toneladas",
             clip: tuple[float, float] | None = CLIP) -> tuple[dict, pd.DataFrame]:
    """La matriz de 2018 llevada a `anio`, producto por producto, con lo medido por zona donde hay fuente y el driver nacional donde no.

    `measured_tables` es la tabla larga de `sources` (anio, origen, destino, producto, t, fuente);
    `grupo_de` dice a qué grupo pertenece cada producto medido (por defecto `sources.GRUPO`), porque
    'bovinos' existe en dos grupos. Un producto medido en `anio` pero no en `base` se escala primero
    con su driver hasta el primer año medido y desde ahí con la fuente. Con `arena_t` se suma la arena
    de fractura que la matriz no vio, en toneladas o en camiones según `unidad`.
    Devuelve las matrices y el estado: anio, grupo, producto, tipo, fuente, factor_nacional.
    """
    from .drivers import factors
    from .sources import GRUPO

    grupo_de = GRUPO if grupo_de is None else grupo_de
    if isinstance(measured_tables, dict):
        measured_tables = pd.concat([t for t in measured_tables.values() if t is not None and not t.empty], ignore_index=True) if measured_tables else None
    if drivers is not None and anio in drivers.index and base in drivers.index:
        f_drv = factors(drivers, anio, base)
    else:
        f_drv = pd.Series(dtype=float)
    # los drivers están escritos con los nombres de la edición en toneladas; la de camiones los recibe por su nombre canónico
    mapa = dict(PRODUCT_DRIVER)
    for _, p in matrices_2018:
        if p not in mapa and canonical_product(p) in PRODUCT_DRIVER:
            mapa[p] = PRODUCT_DRIVER[canonical_product(p)]
    out, tabla = scale_matrices(matrices_2018, f_drv, mapa)
    tabla = tabla.set_index(["grupo", "producto"])
    estado = []
    for (grupo, producto), m18 in matrices_2018.items():
        m = out[(grupo, producto)]
        fila = tabla.loc[(grupo, producto)]
        tipo = "plano" if fila["driver"] == "sin driver, plano" else "escenario driver"
        fuente = "" if tipo == "plano" else f"driver {fila['driver']}"
        canon = canonical_product(producto)
        medido = None
        if measured_tables is not None and not measured_tables.empty and grupo_de.get(canon, grupo) == grupo:
            t = measured_tables[measured_tables["producto"] == canon]
            if not t.empty and anio in set(t["anio"].astype(int)):
                medido = t
        if medido is not None:
            enlace = _chain_base(medido, anio, base, drivers, mapa.get(producto))
            if enlace is not None:
                b, f_enlace = enlace
                lado = _sides(medido)
                codes = list(m18.index)
                fr = zone_factors(medido, anio, b, "origen", codes, clip) if lado in ("origen", "ambos") else None
                fc = zone_factors(medido, anio, b, "destino", codes, clip) if lado in ("destino", "ambos") else None
                m0 = m18 * f_enlace
                if lado == "ambos":
                    m = ipf(m0, m0.sum(axis=1) * fr, m0.sum(axis=0) * fc)
                elif lado == "origen":
                    m = m0.mul(fr, axis=0)
                else:
                    m = m0.mul(fc, axis=1)
                out[(grupo, producto)] = m
                tipo = f"medido {lado}"
                fuente = str(medido["fuente"].iloc[0]) + ("" if b == base else f" (desde {b}; {base}-{b} con driver {mapa.get(producto)})")
        total18 = float(m18.to_numpy().sum())
        estado.append({"anio": int(anio), "grupo": grupo, "producto": producto, "tipo": tipo, "fuente": fuente,
                       "factor_nacional": float(m.to_numpy().sum() / total18) if total18 > 0 else float("nan")})
    if arena_t is not None:
        if unidad == "camiones":
            ya = sum(float(mm[ARENA_DESTINO].sum()) for (g, p), mm in matrices_2018.items() if p == "arena silicea") * T_POR_CAMION
            out[ARENA_KEY] = sand_trucks(float(arena_t), ya, zone_codes=list(next(iter(matrices_2018.values())).index))
        else:
            out = add_sand(out, float(arena_t))
        estado.append({"anio": int(anio), "grupo": ARENA_KEY[0], "producto": ARENA_KEY[1], "tipo": "medido destino", "fuente": "registro de fractura",
                       "factor_nacional": float("nan")})
    return out, pd.DataFrame(estado, columns=ESTADO_COLS)


def published_state(matrices: dict[tuple[str, str], pd.DataFrame], anio: int, arena: bool = False) -> pd.DataFrame:
    """El estado de un año con matriz publicada: todos sus productos son medidos en las dos puntas por la propia matriz."""
    filas = [{"anio": int(anio), "grupo": g, "producto": p, "tipo": "medido ambos", "fuente": "matriz origen-destino publicada", "factor_nacional": float("nan")}
             for (g, p) in matrices if (g, p) != ARENA_KEY]
    if arena:
        filas.append({"anio": int(anio), "grupo": ARENA_KEY[0], "producto": ARENA_KEY[1], "tipo": "medido destino", "fuente": "registro de fractura", "factor_nacional": float("nan")})
    return pd.DataFrame(filas, columns=ESTADO_COLS)


def summarize_state(estado: pd.DataFrame) -> pd.DataFrame:
    """Por año: cuántos productos son medidos, escenario con driver o planos."""
    e = estado.copy()
    e["clase"] = np.where(e["tipo"].str.startswith("medido"), "n_medidos", np.where(e["tipo"] == "plano", "n_plano", "n_escenario"))
    g = e.groupby(["anio", "clase"]).size().unstack("clase").fillna(0).astype(int)
    return g.reindex(columns=["n_medidos", "n_escenario", "n_plano"], fill_value=0)


__all__ = ["CLIP", "ESTADO_COLS", "ARENA_KEY", "ALIAS", "canonical_product", "ipf", "zone_factors", "graduate", "published_state", "summarize_state"]
