"""La matriz de 2018 llevada a otro año: cada producto escalado con su driver, y la arena que la matriz no vio, sumada.

No es un pronóstico. Es "cómo sería la matriz de 2018 con los volúmenes de
otro año": misma estructura de orígenes y destinos, otro tamaño por producto.
Lo que no tiene driver queda igual que en 2018 y se declara.
"""

from __future__ import annotations

import pandas as pd

from .od import structural_empty

# qué driver escala cada producto de la matriz (nombres como los devuelve od.clean_name); lo que no está, queda plano
PRODUCT_DRIVER = {
    # granos y regionales con producción por campaña
    "soja": "soja", "maiz": "maiz", "trigo": "trigo", "girasol": "girasol", "cebada": "cebada", "sorgo": "sorgo", "arroz": "arroz",
    "varios 1": "soja", "varios 2": "maiz", "varios 3": "trigo",
    "limon": "limon", "naranja": "naranja", "mandarina": "mandarina", "pomelo": "pomelo", "algodon": "algodon", "papas": "papas",
    "te": "te", "yerba": "yerba", "azucar": "azucar",
    # combustibles con ventas
    "diesel": "gasoil", "biodiesel": "gasoil", "nafta": "nafta", "bioetanol": "nafta", "grupo combust.": "gasoil", "otros combust": "gasoil", "lubricantes": "gasoil",
    # semiterminados e industrializados con producción
    "cemento": "cemento", "acero": "siderurgia", "vehiculos": "automotriz", "motos": "automotriz", "maq. agricola": "ipi",
    "aluminio primario": "ipi", "aluminio elab.": "ipi", "caucho": "ipi", "papel": "ipi", "plastico": "ipi", "ind. maderera": "isac", "semiterminados": "ipi",
    "aceites": "soja", "harina": "trigo", "fertilizantes": "soja", "electronica": "ipi", "lacteos": "ipi", "cigarrillos": "ipi",
    # minería ligada a la construcción; la arena silícea tiene su propio tratamiento
    "arena const.": "isac", "canto rodado": "isac", "trit. petreos": "isac", "caliza": "cemento", "yeso": "isac", "conchilla": "isac",
    "arcillas": "isac", "arena silicea": "arena_t",
}

# de dónde a dónde va la arena de fractura que la matriz de 2018 no vio: las canteras del sur de Entre Ríos a Neuquén
ARENA_ORIGEN, ARENA_DESTINO = "EGU", "QCP"


def scale_matrices(matrices: dict[tuple[str, str], pd.DataFrame], factores: pd.Series, mapa: dict[str, str] = PRODUCT_DRIVER) -> tuple[dict, pd.DataFrame]:
    """Escala cada matriz por el factor de su driver. Devuelve las matrices y una tabla con el factor usado por producto."""
    out, filas = {}, []
    for (grupo, producto), m in matrices.items():
        drv = mapa.get(producto)
        f = float(factores.get(drv)) if drv is not None and pd.notna(factores.get(drv)) else 1.0
        out[(grupo, producto)] = m * f
        filas.append({"grupo": grupo, "producto": producto, "driver": drv or "sin driver, plano", "factor": round(f, 3)})
    return out, pd.DataFrame(filas)


def add_sand(matrices: dict[tuple[str, str], pd.DataFrame], arena_t: float, origen: str = ARENA_ORIGEN, destino: str = ARENA_DESTINO) -> dict:
    """Suma la arena de fractura del registro como flujo propio, descontando lo que la matriz ya tenía hacia el destino.

    La matriz de 2018 registraba unas 40.000 t de arena silícea hacia Neuquén contra
    934.000 del registro: lo que falta entra como un producto aparte, origen Entre Ríos.
    """
    out = dict(matrices)
    ya = 0.0
    for (g, p), m in matrices.items():
        if p == "arena silicea":
            ya += float(m[destino].sum())
    extra = max(0.0, arena_t - ya)
    base = next(iter(matrices.values()))
    m = pd.DataFrame(0.0, index=base.index, columns=base.columns)
    m.loc[origen, destino] = extra
    out[("mineria arena de fractura", "arena de fractura no vista")] = m
    return out


def empties_by_group(matrices: dict[tuple[str, str], pd.DataFrame]) -> pd.DataFrame:
    """Vacío estructural por grupo: total entre zonas, emparejado y sin vuelta, sumando productos."""
    filas = []
    for (grupo, producto), m in matrices.items():
        e = structural_empty(m)
        filas.append({"grupo": grupo, "producto": producto, "total": e["total"], "emparejado": e["emparejado"], "vacio": e["vacio_estructural"]})
    d = pd.DataFrame(filas)
    g = d.groupby("grupo")[["total", "emparejado", "vacio"]].sum()
    g["pct_sin_vuelta"] = 100.0 * g["vacio"] / g["total"].where(g["total"] > 0)
    return g.sort_values("total", ascending=False)


def yearly(matrices_2018: dict, drivers: pd.DataFrame, arena: pd.Series, anios: tuple[int, ...], base: int = 2018) -> pd.DataFrame:
    """Para cada año: la matriz de 2018 escalada, con la arena sumada, y su vacío total y por grupo."""
    from .drivers import factors

    filas = []
    for a in anios:
        f = factors(drivers, a, base)
        m, _ = scale_matrices(matrices_2018, f)
        m = add_sand(m, float(arena.get(a, 0.0)))
        g = empties_by_group(m)
        total = g[["total", "emparejado", "vacio"]].sum()
        filas.append({"anio": a, "total_mt": total["total"] / 1e6, "vacio_mt": total["vacio"] / 1e6, "pct_sin_vuelta": 100 * total["vacio"] / total["total"],
                      **{f"pct_{k}": v for k, v in g["pct_sin_vuelta"].round(1).items()}})
    return pd.DataFrame(filas).set_index("anio")


__all__ = ["PRODUCT_DRIVER", "ARENA_ORIGEN", "ARENA_DESTINO", "scale_matrices", "add_sand", "empties_by_group", "yearly"]
