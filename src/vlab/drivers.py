"""Los drivers de la proyección: series abiertas que dicen cuánto se movió cada carga después de 2018.

La matriz origen-destino termina en 2018. Para llevarla a los años siguientes
no se extrapola una recta: cada producto se escala con la serie pública que
mejor lo representa. Granos con la producción por campaña del Ministerio de
Agricultura; combustibles con las ventas de gasoil y nafta; cemento con los
despachos; el resto de la industria con el índice de producción del INDEC y
la construcción con el ISAC; y la arena de fractura con el registro de
fractura. Todo sale de la API de series de tiempo del Estado o de un CSV
abierto, y queda cacheado en `data/raw`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import requests

from . import DATA_RAW

API = "https://apis.datos.gob.ar/series/api/series/"

# id en la API, cómo se agrega el año (suma de flujos, promedio de índices) y para qué sirve
SERIES = {
    "gasoil": {"id": "363.3_VENTAS_DE_OIL__16", "agg": "sum", "que": "ventas de gasoil, miles de m³ (Secretaría de Energía)"},
    "nafta": {"id": "363.3_VENTAS_DE_RON_II__33", "agg": "sum", "que": "ventas de nafta súper, miles de m³"},
    "cemento": {"id": "41.3_CP_0_A_16", "agg": "sum", "que": "despachos de cemento portland, miles de t (AFCP)"},
    "ipi": {"id": "453.1_SERIE_ORIGNAL_0_0_14_46", "agg": "mean", "que": "índice de producción industrial manufacturero, INDEC (desde 2016)"},
    "isac": {"id": "33.2_ISAC_NIVELRAL_0_M_18_63", "agg": "mean", "que": "indicador sintético de la actividad de la construcción, INDEC"},
    "siderurgia": {"id": "453.2_INDUSTRIA_ICA_0_0_21_100", "agg": "mean", "que": "IPI industria siderúrgica, INDEC (desde 2016)"},
    "automotriz": {"id": "309.1_PRODUCCIONDES_0_M_30", "agg": "sum", "que": "producción automotriz, unidades (ADEFA)"},
}


def fetch_series(keys: tuple[str, ...] | None = None, start: int = 2010, cache: Path | None = DATA_RAW / "series_api.json", timeout: int = 60, min_meses: int = 6) -> pd.DataFrame:
    """Valores anuales de cada serie, año x driver, agregados según la serie; el año en curso se anualiza si tiene al menos `min_meses`. Con caché en disco."""
    keys = keys or tuple(SERIES)
    cached = json.loads(Path(cache).read_text(encoding="utf-8")) if cache and Path(cache).exists() else {}
    out = {}
    for k in keys:
        s = SERIES[k]
        if k not in cached:
            r = requests.get(API, params={"ids": s["id"], "start_date": str(start), "format": "json", "limit": 1000},
                             timeout=timeout, headers={"User-Agent": "vacio-lab/0.1 (+https://github.com/dpinero14)"})
            r.raise_for_status()
            cached[k] = r.json()["data"]
            if cache:
                Path(cache).parent.mkdir(parents=True, exist_ok=True)
                Path(cache).write_text(json.dumps(cached), encoding="utf-8")
        df = pd.DataFrame(cached[k], columns=["fecha", "valor"]).dropna()
        df["anio"] = df["fecha"].str[:4].astype(int)
        # un año con menos de seis meses se descarta; con seis a once, las sumas se anualizan (los promedios no hace falta)
        meses = df.groupby("anio").size()
        anual = df.groupby("anio")["valor"].agg(s["agg"])
        if (meses > 1).any():
            anual = anual[meses >= min_meses]
            if s["agg"] == "sum":
                anual = anual * (12.0 / meses.reindex(anual.index).clip(upper=12))
        out[k] = anual
    return pd.DataFrame(out).sort_index()


# cultivos del CSV de MAGyP que entran en cada producto de la matriz de granos
GRANOS = {"soja": ["soja total"], "maiz": ["maíz"], "trigo": ["trigo total"], "girasol": ["girasol"], "cebada": ["cebada total"],
          "sorgo": ["sorgo"], "arroz": ["arroz"], "limon": ["limón"], "naranja": ["naranja"], "mandarina": ["mandarina"], "pomelo": ["pomelo"],
          "algodon": ["algodón"], "papas": ["papa total"], "te": ["té"], "yerba": ["yerba mate"], "azucar": ["caña de azúcar"]}


def grain_production(path: Path = DATA_RAW / "magyp_estimaciones_agricolas.csv") -> pd.DataFrame:
    """Producción nacional por producto y año, en toneladas. La campaña 2018/2019 se cuenta como 2019, que es cuando se cosecha y se mueve el grueso."""
    df = pd.read_csv(path, usecols=["cultivo", "campania", "produccion_tm"])
    df["cultivo"] = df["cultivo"].str.lower()
    df["anio"] = df["campania"].str[-4:].astype(int)
    df["produccion_tm"] = pd.to_numeric(df["produccion_tm"], errors="coerce").fillna(0.0)
    out = {}
    for producto, cultivos in GRANOS.items():
        out[producto] = df[df["cultivo"].isin(cultivos)].groupby("anio")["produccion_tm"].sum()
    return pd.DataFrame(out).sort_index()


def sand_by_year(path: Path = DATA_RAW / "fractura_adjunto_iv.csv", basin: str = "NEUQUINA") -> pd.Series:
    """Arena bombeada por año en la cuenca, nacional más importada, en toneladas: el flujo que la matriz no ve."""
    cols = {"fecha_inicio_fractura": "frac_start", "cuenca": "basin", "tipo_reservorio": "reservoir_type",
            "arena_bombeada_nacional_tn": "nac", "arena_bombeada_importada_tn": "imp"}
    df = pd.read_csv(path, low_memory=False, usecols=list(cols)).rename(columns=cols)
    df["anio"] = pd.to_datetime(df["frac_start"], errors="coerce").dt.year
    f = df[(df["basin"].str.upper() == basin) & (df["reservoir_type"].str.upper() == "NO CONVENCIONAL")].copy()
    f["fecha"] = pd.to_datetime(f["frac_start"], errors="coerce")
    t = (f["nac"].fillna(0) + f["imp"].fillna(0)).groupby(f["anio"]).sum().dropna().rename("arena_t")
    # el último año está incompleto y el registro se carga con meses de atraso: se anualiza por los meses
    # con volumen real (al menos el 10 % del mejor mes del año), no por fechas sueltas ni por la fecha de carga
    ultimo = int(t.index.max())
    por_mes = (f.loc[f["anio"] == ultimo, "nac"].fillna(0) + f.loc[f["anio"] == ultimo, "imp"].fillna(0)).groupby(f.loc[f["anio"] == ultimo, "fecha"].dt.month).sum()
    meses = int((por_mes >= 0.1 * por_mes.max()).sum()) if len(por_mes) else 12
    if 1 <= meses < 12:
        t.loc[ultimo] = float(por_mes[por_mes >= 0.1 * por_mes.max()].sum()) * 12.0 / meses
    return t


def driver_table(start: int = 2012, cache: Path | None = DATA_RAW / "series_api.json") -> pd.DataFrame:
    """Todos los drivers en una tabla año x driver: series de la API, granos por producto y arena."""
    api = fetch_series(start=start, cache=cache)
    granos = grain_production()
    arena = sand_by_year()
    t = api.join(granos, how="outer").join(arena, how="outer")
    return t[t.index >= start].sort_index()


def factors(drivers: pd.DataFrame, anio: int, base: int = 2018) -> pd.Series:
    """Factor de cada driver entre el año base y el pedido; NaN si falta alguno de los dos."""
    if anio not in drivers.index or base not in drivers.index:
        raise KeyError(f"no hay drivers para {anio} o {base}")
    return (drivers.loc[anio] / drivers.loc[base]).rename(f"factor_{anio}_vs_{base}")


__all__ = ["SERIES", "GRANOS", "fetch_series", "grain_production", "sand_by_year", "driver_table", "factors"]
