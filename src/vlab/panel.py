"""El panel de flotas: una semana de viajes por vehículo, cargado o vacío, y lo que se puede publicar sin exponer a nadie.

Es la medición que en Argentina nadie hace y que en el Reino Unido sostiene la estadística
oficial de vacío (la encuesta continua CSRGT: una semana por vehículo sorteado). Acá la
versión mínima: cada flota que quiera aportar carga una planilla con sus viajes de una
semana (`panel/plantilla_semana_flota.csv`), y estas funciones la validan, calculan el
vacío por flota, por ruta y por equipo, y agregan lo que se publica con una regla fija:
ningún número sale si detrás hay menos de tres flotas.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

COLUMNAS = ["flota", "vehiculo", "equipo", "fecha", "origen", "destino", "ruta", "km", "cargado", "producto", "toneladas"]
EQUIPOS = ("tolva", "batea", "cisterna", "jaula", "frio", "general", "contenedor", "otro")
MIN_FLOTAS = 3          # regla de publicación: por debajo de esto, la celda no se publica


def read_panel(path: str | Path) -> pd.DataFrame:
    """Lee una o varias planillas del panel y las valida: columnas, equipo conocido, km positivos, cargado 0/1."""
    df = pd.read_csv(path, dtype={"flota": str, "vehiculo": str, "equipo": str, "origen": str, "destino": str, "ruta": str, "producto": str})
    faltan = [c for c in COLUMNAS if c not in df.columns]
    if faltan:
        raise ValueError(f"faltan columnas: {faltan}")
    df["equipo"] = df["equipo"].str.lower().str.strip()
    malos = sorted(set(df["equipo"]) - set(EQUIPOS))
    if malos:
        raise ValueError(f"equipos desconocidos: {malos}; usar {EQUIPOS}")
    df["km"] = pd.to_numeric(df["km"], errors="coerce")
    df["cargado"] = pd.to_numeric(df["cargado"], errors="coerce")
    df["toneladas"] = pd.to_numeric(df["toneladas"], errors="coerce").fillna(0.0)
    if (df["km"] <= 0).any() or df["km"].isna().any():
        raise ValueError("todos los viajes necesitan km positivos")
    if not df["cargado"].isin([0, 1]).all():
        raise ValueError("cargado tiene que ser 0 o 1")
    df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
    return df[COLUMNAS]


def empty_share(df: pd.DataFrame, por: list[str] | None = None) -> pd.DataFrame:
    """Kilómetros vacíos sobre kilómetros totales, por las columnas pedidas (o total), con flotas, vehículos y viajes detrás."""
    d = df.assign(km_vacio=df["km"] * (1 - df["cargado"]))
    if not por:
        g = pd.DataFrame([{"km": d["km"].sum(), "km_vacio": d["km_vacio"].sum(), "flotas": d["flota"].nunique(), "vehiculos": d["vehiculo"].nunique(), "viajes": len(d)}])
    else:
        g = d.groupby(por).agg(km=("km", "sum"), km_vacio=("km_vacio", "sum"), flotas=("flota", "nunique"), vehiculos=("vehiculo", "nunique"), viajes=("km", "size")).reset_index()
    g["pct_vacio"] = 100.0 * g["km_vacio"] / g["km"].where(g["km"] > 0)
    return g


def publishable(tabla: pd.DataFrame, min_flotas: int = MIN_FLOTAS) -> pd.DataFrame:
    """Lo que se puede publicar: filas con al menos `min_flotas` flotas detrás; el resto queda con los valores tapados."""
    out = tabla.copy()
    tapar = out["flotas"] < min_flotas
    for c in ("km", "km_vacio", "pct_vacio", "vehiculos", "viajes"):
        out.loc[tapar, c] = float("nan")
    out["publicable"] = ~tapar
    return out


def week_report(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """El informe de una semana: total, por equipo, por ruta y por flota (esta última solo para devolverle a cada flota lo suyo)."""
    return {"total": empty_share(df), "por_equipo": publishable(empty_share(df, ["equipo"])), "por_ruta": publishable(empty_share(df, ["ruta"])),
            "por_flota": empty_share(df, ["flota"])}


__all__ = ["COLUMNAS", "EQUIPOS", "MIN_FLOTAS", "read_panel", "empty_share", "publishable", "week_report"]
