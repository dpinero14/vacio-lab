"""Las fuentes que miden un producto zona por zona después de 2018: lectores que devuelven todos la misma tabla larga.

La matriz origen-destino termina en 2018. Para algunos productos existe una
fuente abierta que sigue midiendo el flujo, y con más detalle que un driver
nacional: SENASA registra cada movimiento de hacienda entre departamentos
(origen y destino), la Secretaría de Energía publica el volumen vendido por
cada estación de servicio (destino del combustible), la AFCP el consumo de
cemento por provincia (destino), y el Ministerio de Agricultura la producción
por departamento y campaña (origen del grano). Cada lector devuelve `anio,
origen, destino, producto, t, fuente`, con `origen` o `destino` en None cuando
esa punta no se mide. Los años parciales se anualizan como los drivers: con
seis meses o más se escala por 12/n; con menos, el año no cuenta.
"""

from __future__ import annotations

import io
import re
from pathlib import Path

import numpy as np
import pandas as pd

from . import DATA_PROC, DATA_RAW
from .drivers import GRANOS
from .zoning import CABA, CABA_ID, PROVINCIA_ZONA, department_zones, locality_zones, normalize, province_to_zones

COLUMNAS = ["anio", "origen", "destino", "producto", "t", "fuente"]
MIN_MESES = 6

# peso vivo medio por categoría, en kg, para pasar cabezas a toneladas (órdenes de magnitud usuales de la ganadería pampeana)
PESO_KG = {"vaca": 450.0, "vaquillona": 300.0, "novillo": 430.0, "novillito": 330.0, "ternero": 180.0, "ternera": 180.0, "torito": 350.0, "toro": 600.0, "bueyes": 600.0}
# densidad para pasar m³ vendidos a toneladas
DENSIDAD_T_M3 = {"diesel": 0.84, "nafta": 0.74}
# producto de la Res. 1104 -> producto de la matriz; el GNC y el resto no entran
EESS_PRODUCTOS = {"Gas Oil Grado 2": "diesel", "Gas Oil Grado 3": "diesel", "Nafta (súper) entre 92 y 95 Ron": "nafta",
                  "Nafta (premium) de más de 95 Ron": "nafta", "Nafta (común) hasta 92 Ron": "nafta"}
EESS_CANAL_EXCLUIDO = "Reventa a otras estaciones de servicio"   # se contaría dos veces: en la que revende y en la que vende
EESS_MAX_M3 = 10000.0                                             # por boca, producto y mes; por encima es un error de carga (litros por m³)
FUENTES = {"bovinos": "SENASA, movimientos de bovinos entre departamentos", "diesel": "Secretaría de Energía, volúmenes por estación de servicio (Res. 1104/04)",
           "nafta": "Secretaría de Energía, volúmenes por estación de servicio (Res. 1104/04)", "cemento": "AFCP, consumo de cemento por provincia",
           "granos": "MAGyP, estimaciones agrícolas por departamento"}
# el nombre del producto en la matriz cuando difiere de la clave de drivers.GRANOS
PRODUCTO_MATRIZ = {"te": "té"}
# a qué grupo de la matriz pertenece cada producto medido: 'bovinos' existe también en carnes, y ese no se mide acá
GRUPO = {"bovinos": "ganado en pie", "diesel": "combustibles", "nafta": "combustibles", "cemento": "semiterminados",
         **{PRODUCTO_MATRIZ.get(g, g): ("granos" if g in ("soja", "maiz", "trigo", "girasol", "cebada", "sorgo", "arroz") else "regionales") for g in GRANOS}}
MESES = {m: i + 1 for i, m in enumerate(("ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO", "JULIO", "AGOSTO", "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE"))}
MESES["SETIEMBRE"] = 9


def _empty() -> pd.DataFrame:
    return pd.DataFrame(columns=COLUMNAS)


def annualize(df: pd.DataFrame, meses: int, min_meses: int = MIN_MESES) -> pd.DataFrame:
    """Escala `t` por 12/meses si hay al menos `min_meses`; con menos devuelve la tabla vacía."""
    if meses < min_meses:
        return _empty()
    out = df.copy()
    if meses < 12:
        out["t"] = out["t"] * (12.0 / meses)
    return out


def _dept_maps(dz: pd.DataFrame) -> tuple[dict, dict]:
    """De la tabla de department_zones: id -> zona, y (provincia, departamento normalizados) -> zona."""
    por_id = dict(zip(dz["departamento_id"], dz["codigo"]))
    por_nombre = {(normalize(p), normalize(d)): c for p, d, c in zip(dz["provincia"], dz["departamento"], dz["codigo"])}
    return por_id, por_nombre


def _zone_of(prov_id: pd.Series, dept_id: pd.Series, prov: pd.Series, dept: pd.Series, dz: pd.DataFrame) -> pd.Series:
    """Zona de cada fila: por id de departamento, si no por nombre dentro de la provincia; la Ciudad va a BCP."""
    por_id, por_nombre = _dept_maps(dz)
    ids = dept_id.astype(str).str.zfill(5)
    out = ids.map(por_id)
    faltan = out.isna()
    if faltan.any():
        # cuando el id no está en georef (departamentos que cambiaron de código), se busca por nombre dentro de la provincia
        claves = [(normalize(PROVINCIA_ZONA.get(str(pi).zfill(2), p)), normalize(d)) for pi, p, d in zip(prov_id[faltan], prov[faltan], dept[faltan])]
        out[faltan] = [por_nombre.get(k) for k in claves]
    out[prov_id.astype(str).str.zfill(2) == CABA_ID] = CABA
    return out


def cattle_movements(anio: int, raw: Path = DATA_RAW, zonas: pd.DataFrame | None = None, dz: pd.DataFrame | None = None, path: Path | None = None) -> pd.DataFrame:
    """Bovinos movidos entre zonas en un año, en toneladas de peso vivo, con origen y destino (SENASA).

    Solo cuentan los movimientos entre departamentos distintos: lo que se mueve dentro de un
    departamento no recorre un corredor. Las cabezas se pasan a toneladas con `PESO_KG`.
    """
    path = path or raw / f"senasa_movimientos_bovinos_{anio}.csv"
    if not Path(path).exists():
        return _empty()
    cols = ["fecha", "provincia_origen", "provincia_origen_id", "departamento_origen", "departamento_origen_id",
            "provincia_destino", "provincia_destino_id", "departamento_destino", "departamento_destino_id", *PESO_KG]
    df = pd.read_csv(path, encoding="latin-1", usecols=cols, dtype={c: str for c in cols if c.endswith("_id") or c in ("fecha", "provincia_origen", "provincia_destino", "departamento_origen", "departamento_destino")})
    meses = int(df["fecha"].astype(str).str[:7].nunique())      # los meses que trae el archivo, antes de filtrar
    df = df.dropna(subset=["departamento_origen_id", "departamento_destino_id"])
    df = df[df["departamento_origen_id"] != df["departamento_destino_id"]].copy()
    if df.empty:
        return _empty()
    if dz is None:
        from .od import zones
        dz = department_zones(zones() if zonas is None else zonas)
    df["origen"] = _zone_of(df["provincia_origen_id"], df["departamento_origen_id"], df["provincia_origen"], df["departamento_origen"], dz)
    df["destino"] = _zone_of(df["provincia_destino_id"], df["departamento_destino_id"], df["provincia_destino"], df["departamento_destino"], dz)
    df["t"] = sum(pd.to_numeric(df[c], errors="coerce").fillna(0.0) * (kg / 1000.0) for c, kg in PESO_KG.items())
    g = df.dropna(subset=["origen", "destino"]).groupby(["origen", "destino"], as_index=False)["t"].sum()
    g = g[g["t"] > 0]
    g["anio"], g["producto"], g["fuente"] = int(anio), "bovinos", FUENTES["bovinos"]
    return annualize(g[COLUMNAS], meses)


def _sniff(path: Path, encoding: str) -> str:
    with open(path, encoding=encoding, errors="replace") as f:
        primera = f.readline()
    return ";" if primera.count(";") > primera.count(",") else ","


def read_eess(path: Path) -> pd.DataFrame:
    """Un archivo de la Res. 1104 reducido a anio, mes, localidad, provincia, producto (de la matriz), m3, con los dos formatos que usó la fuente.

    Deja afuera el GNC y los demás productos, la reventa entre estaciones y las filas por
    encima de `EESS_MAX_M3` por boca y mes, que son errores de unidad.
    """
    path = Path(path)
    encoding = "utf-8-sig"
    try:
        sep = _sniff(path, encoding)
        head = pd.read_csv(path, encoding=encoding, sep=sep, nrows=5)
    except UnicodeDecodeError:
        encoding = "latin-1"
        sep = _sniff(path, encoding)
        head = pd.read_csv(path, encoding=encoding, sep=sep, nrows=5)
    quiero = {"anio", "mes", "periodo", "fecha", "localidad", "provincia", "producto", "canal_de_comercializacion", "volumen"}
    usar = [c for c in head.columns if c.strip().lower() in quiero]
    df = pd.read_csv(path, encoding=encoding, sep=sep, usecols=usar, low_memory=False)
    df.columns = [c.strip().lower() for c in df.columns]
    if "periodo" in df.columns:
        per = df["periodo"].astype(str).str.replace("/", "-", regex=False)
        df["anio"] = pd.to_numeric(per.str[:4], errors="coerce")
        df["mes"] = pd.to_numeric(per.str[5:7], errors="coerce")
    elif "anio" not in df.columns and "fecha" in df.columns:
        f = pd.to_datetime(df["fecha"], errors="coerce")
        df["anio"], df["mes"] = f.dt.year, f.dt.month
    df["anio"] = pd.to_numeric(df["anio"], errors="coerce")
    df["mes"] = pd.to_numeric(df["mes"], errors="coerce")
    df["producto"] = df["producto"].map(EESS_PRODUCTOS)
    df = df.dropna(subset=["producto", "anio", "mes"])
    if "canal_de_comercializacion" in df.columns:
        df = df[df["canal_de_comercializacion"] != EESS_CANAL_EXCLUIDO]
    df["m3"] = pd.to_numeric(df["volumen"], errors="coerce")
    df = df[(df["m3"] > 0) & (df["m3"] <= EESS_MAX_M3)]
    g = df.groupby(["anio", "mes", "localidad", "provincia", "producto"], as_index=False)["m3"].sum()
    g["anio"], g["mes"] = g["anio"].astype(int), g["mes"].astype(int)
    return g


def eess_file(anio: int, raw: Path = DATA_RAW) -> Path:
    """El archivo de la Res. 1104 que cubre un año: uno por año hasta 2024, y desde diciembre de 2024 uno solo en `eess_2025.csv`."""
    return raw / f"eess_{min(int(anio), 2025)}.csv"


def eess_by_locality(anio: int, raw: Path = DATA_RAW, cache_dir: Path | None = DATA_PROC) -> pd.DataFrame:
    """Volumen por localidad, producto y mes de un año, con caché en `cache_dir` porque los archivos pesan 60 a 130 MB."""
    cache = Path(cache_dir) / f"eess_localidad_{anio}.csv" if cache_dir else None
    if cache and cache.exists():
        return pd.read_csv(cache)
    path = eess_file(anio, raw)
    if not path.exists():
        return pd.DataFrame(columns=["anio", "mes", "localidad", "provincia", "producto", "m3"])
    g = read_eess(path)
    g = g[g["anio"] == int(anio)].reset_index(drop=True)
    if cache:
        cache.parent.mkdir(parents=True, exist_ok=True)
        g.to_csv(cache, index=False)
    return g


def fuel_by_zone(anio: int, raw: Path = DATA_RAW, zonas: pd.DataFrame | None = None, cache_dir: Path | None = DATA_PROC,
                 localidades: pd.DataFrame | None = None, fetch: bool = True) -> pd.DataFrame:
    """Gasoil y nafta vendidos en las estaciones de cada zona en un año, en toneladas, del lado del destino.

    Cada localidad va a su zona con `zoning.locality_zones` (georef, cacheado); `localidades`
    permite pasar ese mapa ya resuelto. Sin `fetch`, las localidades sin caché caen a la provincia.
    """
    g = eess_by_locality(anio, raw, cache_dir)
    if g.empty:
        return _empty()
    g["loc_n"], g["prov_n"] = g["localidad"].map(normalize), g["provincia"].map(normalize)
    if localidades is None:
        localidades = locality_zones(list(zip(g["loc_n"], g["prov_n"])), zonas=zonas, fetch=fetch, cache_path=raw / "georef_localidades.json")
    mapa = {(l, p): c for l, p, c in zip(localidades["localidad"], localidades["provincia"], localidades["codigo"])}
    g["destino"] = [mapa.get((l, p)) for l, p in zip(g["loc_n"], g["prov_n"])]
    g["t"] = g["m3"] * g["producto"].map(DENSIDAD_T_M3)
    meses = int(g["mes"].nunique())
    out = g.dropna(subset=["destino"]).groupby(["destino", "producto"], as_index=False)["t"].sum()
    out["anio"], out["origen"] = int(anio), None
    out["fuente"] = out["producto"].map(FUENTES)
    return annualize(out[COLUMNAS], meses)


def _num(v) -> float:
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    s = str(v).strip().replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return float("nan")


def parse_afcp_html(html: str) -> pd.DataFrame:
    """La tabla de consumo de cemento por provincia de una página mensual de la AFCP: anio, mes, provincia, t (total del mes).

    Cada página trae el mes pedido y, más abajo, el mismo mes del año anterior; se leen los dos.
    Las provincias vienen en mayúsculas y con espacios dobles, que se colapsan.
    """
    try:
        tablas = pd.read_html(io.StringIO(html), thousands=".", decimal=",", flavor="lxml")
    except (ValueError, ImportError):          # una página sin tabla (un 404 disfrazado) no es un error: no hay datos
        return pd.DataFrame(columns=["anio", "mes", "provincia", "t"])
    rows = []
    for t in tablas:
        anio = mes = col_total = None
        for _, r in t.iterrows():
            celdas = [normalize(c) if pd.notna(c) else "" for c in r.tolist()]
            m = re.search(r"PERIODO:\s*([A-Z]+)\s+DE\s+(\d{4})", celdas[0])
            if m:
                anio, mes, col_total = int(m.group(2)), MESES.get(m.group(1)), None
                continue
            if "TOTALES" in celdas[1:] and celdas[0] == "PROVINCIAS":
                col_total = celdas.index("TOTALES")
                continue
            if anio is None or mes is None or col_total is None or not celdas[0] or celdas[0] in ("PROVINCIAS", "TOTALES", "DEL MES"):
                continue
            v = _num(r.iloc[col_total])
            if np.isnan(v):
                continue
            rows.append({"anio": anio, "mes": mes, "provincia": celdas[0], "t": v})
    return pd.DataFrame(rows, columns=["anio", "mes", "provincia", "t"]).drop_duplicates(["anio", "mes", "provincia"]).reset_index(drop=True)


def cement_by_zone(anio: int, raw: Path = DATA_RAW, zonas: pd.DataFrame | None = None, path: Path | None = None) -> pd.DataFrame:
    """Cemento consumido en cada zona en un año, en toneladas, del lado del destino (AFCP por provincia).

    El reparto dentro de la provincia es uniforme entre sus zonas: la fuente no distingue más, así
    que el factor de cada zona termina siendo el de su provincia. Capital y Gran Buenos Aires van
    a las zonas del conurbano; 'Buenos Aires' al resto de la provincia.
    """
    path = path or raw / "afcp_provincias.csv"
    if not Path(path).exists():
        return _empty()
    df = pd.read_csv(path)
    df = df[df["anio"] == int(anio)]
    if df.empty:
        return _empty()
    if zonas is None:
        from .od import zones
        zonas = zones()
    pz = province_to_zones(zonas)
    meses = int(df["mes"].nunique())
    rows = []
    for prov, t in df.groupby("provincia")["t"].sum().items():
        zs = pz.get(normalize(prov))
        if not zs:
            continue
        for z in zs:
            rows.append({"anio": int(anio), "origen": None, "destino": z, "producto": "cemento", "t": float(t) / len(zs), "fuente": FUENTES["cemento"]})
    out = pd.DataFrame(rows, columns=COLUMNAS).groupby(["anio", "destino", "producto", "fuente"], as_index=False, dropna=False)["t"].sum()
    out["origen"] = None
    return annualize(out[COLUMNAS], meses)


def grains_by_zone(anio: int, raw: Path = DATA_RAW, zonas: pd.DataFrame | None = None, dz: pd.DataFrame | None = None, path: Path | None = None) -> pd.DataFrame:
    """Producción de cada grano y cultivo regional por zona de origen en un año (campaña X/Y cuenta como Y, como en `drivers`).

    Los departamentos van a su zona por id de georef y, si no, por nombre dentro de la provincia.
    """
    path = path or raw / "magyp_estimaciones_agricolas.csv"
    if not Path(path).exists():
        return _empty()
    df = pd.read_csv(path, usecols=["cultivo", "campania", "provincia", "provincia_id", "departamento", "departamento_id", "produccion_tm"],
                     dtype={"provincia_id": str, "departamento_id": str})
    df["anio"] = pd.to_numeric(df["campania"].astype(str).str[-4:], errors="coerce")
    df = df[df["anio"] == int(anio)].copy()
    if df.empty:
        return _empty()
    df["cultivo"] = df["cultivo"].str.lower()
    cultivo_producto = {c: PRODUCTO_MATRIZ.get(p, p) for p, cs in GRANOS.items() for c in cs}
    df["producto"] = df["cultivo"].map(cultivo_producto)
    df = df.dropna(subset=["producto"])
    if dz is None:
        from .od import zones
        dz = department_zones(zones() if zonas is None else zonas)
    df["origen"] = _zone_of(df["provincia_id"], df["departamento_id"], df["provincia"], df["departamento"], dz)
    df["t"] = pd.to_numeric(df["produccion_tm"], errors="coerce").fillna(0.0)
    out = df.dropna(subset=["origen"]).groupby(["origen", "producto"], as_index=False)["t"].sum()
    out = out[out["t"] > 0]
    out["anio"], out["destino"], out["fuente"] = int(anio), None, FUENTES["granos"]
    return out[COLUMNAS].reset_index(drop=True)


def eess_years(raw: Path = DATA_RAW, cache_dir: Path | None = DATA_PROC) -> dict[int, int]:
    """Años con archivo de la Res. 1104 y cuántos meses trae cada uno (los de 2025 en adelante salen de un mismo archivo)."""
    out = {}
    for a in range(2004, 2025):
        if (raw / f"eess_{a}.csv").exists():
            cache = Path(cache_dir) / f"eess_localidad_{a}.csv" if cache_dir else None
            out[a] = int(pd.read_csv(cache, usecols=["mes"])["mes"].nunique()) if cache and cache.exists() else 12
    p = raw / "eess_2025.csv"
    if p.exists():
        cache_ok = cache_dir and all((Path(cache_dir) / f"eess_localidad_{a}.csv").exists() for a in (2025, 2026))
        if cache_ok:
            for a in (2025, 2026):
                out[a] = int(pd.read_csv(Path(cache_dir) / f"eess_localidad_{a}.csv", usecols=["mes"])["mes"].nunique())
        else:
            sep = _sniff(p, "utf-8-sig")
            per = pd.read_csv(p, encoding="utf-8-sig", sep=sep, usecols=["periodo"])["periodo"].astype(str)
            for a, n in per.str[:4].groupby(per.str[:4]).size().items():
                if a.isdigit() and int(a) >= 2025:
                    out[int(a)] = int(per[per.str[:4] == a].nunique())
    return out


def available(raw: Path = DATA_RAW, cache_dir: Path | None = DATA_PROC, min_meses: int = MIN_MESES) -> dict[str, dict]:
    """Qué producto tiene fuente medida y para qué años, según lo que hay en disco: {producto: {grupo, lado, fuente, anios: (min, max), lista}}."""
    out = {}
    senasa = sorted(int(m.group(1)) for p in raw.glob("senasa_movimientos_bovinos_*.csv") for m in [re.search(r"(\d{4})", p.name)] if m)
    if senasa:
        out["bovinos"] = {"grupo": GRUPO["bovinos"], "lado": "ambos", "fuente": FUENTES["bovinos"], "anios": (min(senasa), max(senasa)), "lista": senasa}
    eess = sorted(a for a, n in eess_years(raw, cache_dir).items() if n >= min_meses)
    for p in ("diesel", "nafta"):
        if eess:
            out[p] = {"grupo": GRUPO[p], "lado": "destino", "fuente": FUENTES[p], "anios": (min(eess), max(eess)), "lista": eess}
    afcp = raw / "afcp_provincias.csv"
    if afcp.exists():
        a = pd.read_csv(afcp).groupby("anio")["mes"].nunique()
        cem = sorted(int(k) for k, n in a.items() if n >= min_meses)
        if cem:
            out["cemento"] = {"grupo": GRUPO["cemento"], "lado": "destino", "fuente": FUENTES["cemento"], "anios": (min(cem), max(cem)), "lista": cem}
    magyp = raw / "magyp_estimaciones_agricolas.csv"
    if magyp.exists():
        m = pd.read_csv(magyp, usecols=["cultivo", "campania", "produccion_tm"])
        m["cultivo"] = m["cultivo"].str.lower()
        m["anio"] = pd.to_numeric(m["campania"].astype(str).str[-4:], errors="coerce")
        m["produccion_tm"] = pd.to_numeric(m["produccion_tm"], errors="coerce").fillna(0.0)
        for producto, cultivos in GRANOS.items():
            s = m[m["cultivo"].isin(cultivos)].groupby("anio")["produccion_tm"].sum()
            anios = sorted(int(a) for a, v in s.items() if v > 0 and a >= 2012)
            if anios:
                p = PRODUCTO_MATRIZ.get(producto, producto)
                out[p] = {"grupo": GRUPO[p], "lado": "origen", "fuente": FUENTES["granos"], "anios": (min(anios), max(anios)), "lista": anios}
    return out


def measured_tables(anios: tuple[int, ...], raw: Path = DATA_RAW, zonas: pd.DataFrame | None = None, registry: dict | None = None,
                    cache_dir: Path | None = DATA_PROC, fetch: bool = True, verbose: bool = False) -> pd.DataFrame:
    """Todas las mediciones disponibles para los años pedidos, en una sola tabla larga con las columnas de `COLUMNAS`."""
    from .od import zones

    zonas = zones() if zonas is None else zonas
    registry = available(raw, cache_dir) if registry is None else registry
    dz = department_zones(zonas)
    partes = []
    for a in anios:
        a = int(a)
        if "bovinos" in registry and a in registry["bovinos"]["lista"]:
            partes.append(cattle_movements(a, raw, zonas, dz))
        if "diesel" in registry and a in registry["diesel"]["lista"]:
            partes.append(fuel_by_zone(a, raw, zonas, cache_dir, fetch=fetch))
        if "cemento" in registry and a in registry["cemento"]["lista"]:
            partes.append(cement_by_zone(a, raw, zonas))
        granos = [PRODUCTO_MATRIZ.get(p, p) for p in GRANOS if PRODUCTO_MATRIZ.get(p, p) in registry and a in registry[PRODUCTO_MATRIZ.get(p, p)]["lista"]]
        if granos:
            g = grains_by_zone(a, raw, zonas, dz)
            partes.append(g[g["producto"].isin(granos)])
        if verbose:
            print(f"  {a}: {sum(len(p) for p in partes)} filas acumuladas")
    partes = [p for p in partes if not p.empty]
    if not partes:
        return _empty()
    return pd.concat(partes, ignore_index=True)[COLUMNAS]


__all__ = ["COLUMNAS", "MIN_MESES", "PESO_KG", "DENSIDAD_T_M3", "EESS_PRODUCTOS", "EESS_MAX_M3", "FUENTES", "GRUPO", "PRODUCTO_MATRIZ", "annualize", "cattle_movements",
           "read_eess", "eess_by_locality", "fuel_by_zone", "parse_afcp_html", "cement_by_zone", "grains_by_zone", "eess_years", "available", "measured_tables"]
