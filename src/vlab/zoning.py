"""De departamentos y localidades a zonas de tráfico: el puente entre las fuentes abiertas y la matriz.

La matriz origen-destino usa 123 zonas, cada una un grupo de departamentos con
un centroide geocodificado. Las fuentes que la miden vienen a otra escala:
SENASA por departamento, las estaciones de servicio por localidad, la AFCP por
provincia, el Ministerio de Agricultura por departamento. Este módulo lleva
cada una a la zona: el departamento va a la zona con el centroide más cercano
dentro de su misma provincia; la localidad, a través de su departamento
(georef) o, si no se encuentra, a la zona más cercana al centro de la
provincia; la provincia, a la lista de sus zonas. Los nombres se comparan sin
acentos ni mayúsculas. La Ciudad de Buenos Aires es una zona propia (BCP)
aunque la matriz la cuente dentro de la provincia de Buenos Aires.
"""

from __future__ import annotations

import json
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

from . import DATA_RAW

GEOREF_LOCALIDADES = "https://apis.datos.gob.ar/georef/api/localidades"
CABA = "BCP"                       # el código de zona de la Ciudad de Buenos Aires
CABA_ID = "02"                     # el código INDEC de la Ciudad como provincia
RADIO_GBA_KM = 70.0                # zonas a menos de esto del centro de la Ciudad cuentan como Gran Buenos Aires

# nombre normalizado de cada provincia -> código INDEC, para consultar georef por id y no por nombre
PROVINCIA_ID = {
    "CIUDAD AUTONOMA DE BUENOS AIRES": "02", "CAPITAL FEDERAL": "02", "CABA": "02", "BUENOS AIRES": "06", "CATAMARCA": "10",
    "CORDOBA": "14", "CORRIENTES": "18", "CHACO": "22", "CHUBUT": "26", "ENTRE RIOS": "30", "FORMOSA": "34", "JUJUY": "38",
    "LA PAMPA": "42", "LA RIOJA": "46", "MENDOZA": "50", "MISIONES": "54", "NEUQUEN": "58", "RIO NEGRO": "62", "SALTA": "66",
    "SAN JUAN": "70", "SAN LUIS": "74", "SANTA CRUZ": "78", "SANTA FE": "82", "SANTIAGO DEL ESTERO": "86", "SGO. DEL ESTERO": "86",
    "TUCUMAN": "90", "TIERRA DEL FUEGO": "94", "TIERRA DEL FUEGO, ANTARTIDA E ISLAS DEL ATLANTICO SUR": "94", "T. DEL FUEGO": "94",
}
# id INDEC -> la provincia tal como la escribe la tabla de zonas (mayúsculas, sin acentos)
PROVINCIA_ZONA = {"02": "BUENOS AIRES", "06": "BUENOS AIRES", "10": "CATAMARCA", "14": "CORDOBA", "18": "CORRIENTES", "22": "CHACO", "26": "CHUBUT",
                  "30": "ENTRE RIOS", "34": "FORMOSA", "38": "JUJUY", "42": "LA PAMPA", "46": "LA RIOJA", "50": "MENDOZA", "54": "MISIONES",
                  "58": "NEUQUEN", "62": "RIO NEGRO", "66": "SALTA", "70": "SAN JUAN", "74": "SAN LUIS", "78": "SANTA CRUZ", "82": "SANTA FE",
                  "86": "SANTIAGO DEL ESTERO", "90": "TUCUMAN", "94": "TIERRA DEL FUEGO"}


def normalize(s: str) -> str:
    """'Ciudad Autónoma de Buenos Aires' -> 'CIUDAD AUTONOMA DE BUENOS AIRES': sin acentos, mayúsculas, un solo espacio."""
    t = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return " ".join(t.upper().split())


def province_id(name: str) -> str | None:
    """El código INDEC de una provincia escrita de cualquier manera; None si no la reconoce."""
    return PROVINCIA_ID.get(normalize(name))


def _haversine_km(lon1: float, lat1: float, lons: np.ndarray, lats: np.ndarray) -> np.ndarray:
    p1, p2 = np.radians(lat1), np.radians(lats)
    dl = np.radians(lons - lon1)
    a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * 6371.0 * np.arcsin(np.sqrt(a))


def nearest_zone(lon: float, lat: float, zonas: pd.DataFrame, provincia: str | None = None) -> str | None:
    """La zona con el centroide más cercano a un punto, restringida a una provincia si se pide (nombre como en la tabla de zonas)."""
    z = zonas if provincia is None else zonas[zonas["provincia"] == provincia]
    if z.empty or pd.isna(lon) or pd.isna(lat):
        return None
    d = _haversine_km(float(lon), float(lat), z["lon"].to_numpy(float), z["lat"].to_numpy(float))
    return str(z["codigo"].iloc[int(np.argmin(d))])


def read_georef_departments(path: Path = DATA_RAW / "georef_departamentos.json") -> pd.DataFrame:
    """Los departamentos de georef: departamento_id, departamento, provincia_id, provincia_georef, lon, lat."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    deps = raw["departamentos"] if isinstance(raw, dict) else raw
    rows = [{"departamento_id": d["id"], "departamento": d["nombre"], "provincia_id": d["provincia"]["id"], "provincia_georef": d["provincia"]["nombre"],
             "lon": d["centroide"]["lon"], "lat": d["centroide"]["lat"]} for d in deps]
    return pd.DataFrame(rows, columns=["departamento_id", "departamento", "provincia_id", "provincia_georef", "lon", "lat"])


def department_zones(zonas: pd.DataFrame, georef_path: Path = DATA_RAW / "georef_departamentos.json") -> pd.DataFrame:
    """Cada departamento de georef con su zona: departamento_id, departamento, provincia, codigo.

    La zona es la del centroide más cercano dentro de la misma provincia; `provincia` va
    como en la tabla de zonas (mayúsculas, sin acentos). Las comunas de la Ciudad van a BCP.
    """
    d = read_georef_departments(georef_path)
    d["provincia"] = d["provincia_id"].map(PROVINCIA_ZONA)
    sin_caba = zonas[zonas["codigo"] != CABA]
    codigos = []
    for _, r in d.iterrows():
        if r["provincia_id"] == CABA_ID:
            codigos.append(CABA)
        else:
            codigos.append(nearest_zone(r["lon"], r["lat"], sin_caba, r["provincia"]))
    d["codigo"] = codigos
    return d[["departamento_id", "departamento", "provincia", "codigo"]]


def province_to_zones(zonas: pd.DataFrame, radio_gba_km: float = RADIO_GBA_KM) -> dict[str, list[str]]:
    """Las zonas de cada provincia, por nombre normalizado, con las variantes que usan las fuentes.

    'CAPITAL FEDERAL' y 'GRAN BUENOS AIRES' (como reparte la AFCP) son las zonas de Buenos Aires
    a menos de `radio_gba_km` del centro de la Ciudad, incluida la Ciudad; 'BUENOS AIRES' es el resto.
    """
    out = {p: list(z["codigo"]) for p, z in zonas.groupby("provincia")}
    ba = zonas[zonas["provincia"] == "BUENOS AIRES"]
    c = ba[ba["codigo"] == CABA].iloc[0]
    d = _haversine_km(float(c["lon"]), float(c["lat"]), ba["lon"].to_numpy(float), ba["lat"].to_numpy(float))
    gba = list(ba["codigo"][d <= radio_gba_km])
    out["GRAN BUENOS AIRES"] = gba
    out["CAPITAL FEDERAL"] = gba
    out["CIUDAD AUTONOMA DE BUENOS AIRES"] = gba
    out["BUENOS AIRES"] = [z for z in out["BUENOS AIRES"] if z not in gba]
    for alias, canon in (("SGO. DEL ESTERO", "SANTIAGO DEL ESTERO"), ("T. DEL FUEGO", "TIERRA DEL FUEGO"),
                         ("TIERRA DEL FUEGO, ANTARTIDA E ISLAS DEL ATLANTICO SUR", "TIERRA DEL FUEGO")):
        if canon in out:
            out[alias] = out[canon]
    return out


def province_centroids(georef_path: Path = DATA_RAW / "georef_departamentos.json") -> pd.DataFrame:
    """El centro de cada provincia como promedio de los centroides de sus departamentos: provincia_id, lon, lat."""
    d = read_georef_departments(georef_path)
    return d.groupby("provincia_id")[["lon", "lat"]].mean().reset_index()


def _query_georef(pairs: list[tuple[str, str]], timeout: int = 120) -> dict[str, dict | None]:
    """Consulta georef en tandas de hasta 500 localidades; clave 'PROVINCIA_ID|LOCALIDAD', valor {lon, lat, departamento_id} o None."""
    import requests

    out = {}
    for i in range(0, len(pairs), 500):
        tanda = pairs[i:i + 500]
        body = {"localidades": [{"nombre": loc, "provincia": pid, "max": 1, "campos": "nombre,centroide,departamento.id"} for pid, loc in tanda]}
        r = requests.post(GEOREF_LOCALIDADES, json=body, timeout=timeout, headers={"User-Agent": "vacio-lab/0.1 (+https://github.com/dpinero14)"})
        r.raise_for_status()
        for (pid, loc), res in zip(tanda, r.json()["resultados"]):
            hits = res.get("localidades") or []
            out[f"{pid}|{loc}"] = ({"lon": hits[0]["centroide"]["lon"], "lat": hits[0]["centroide"]["lat"], "departamento_id": (hits[0].get("departamento") or {}).get("id")}
                                   if hits else None)
    return out


def locality_zones(pairs: list[tuple[str, str]] | pd.DataFrame, cache_path: Path = DATA_RAW / "georef_localidades.json", zonas: pd.DataFrame | None = None,
                   georef_path: Path = DATA_RAW / "georef_departamentos.json", fetch: bool = True) -> pd.DataFrame:
    """Cada par (localidad, provincia) con su zona: localidad, provincia, codigo, metodo.

    `metodo` dice cómo se llegó: 'departamento' (georef encontró la localidad y su departamento
    va a una zona), 'centroide' (georef la encontró pero sin departamento útil: zona más cercana
    dentro de la provincia) o 'provincia' (no la encontró: zona más cercana al centro de la
    provincia). Las consultas quedan cacheadas en `cache_path`; con `fetch=False` no consulta.
    Los nombres salen normalizados (mayúsculas, sin acentos), que es como se cachean.
    """
    from .od import zones

    zonas = zones() if zonas is None else zonas
    if isinstance(pairs, pd.DataFrame):
        pairs = list(zip(pairs["localidad"], pairs["provincia"]))
    pares = sorted({(normalize(loc), normalize(prov)) for loc, prov in pairs if pd.notna(loc) and pd.notna(prov)})
    cache_path = Path(cache_path)
    cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
    faltan = []
    for loc, prov in pares:
        pid = PROVINCIA_ID.get(prov)
        if pid is not None and pid != CABA_ID and f"{pid}|{loc}" not in cache:
            faltan.append((pid, loc))
    if faltan and fetch:
        cache.update(_query_georef(faltan))
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    dz = department_zones(zonas, georef_path).set_index("departamento_id")["codigo"].to_dict()
    centros = province_centroids(georef_path).set_index("provincia_id")
    sin_caba = zonas[zonas["codigo"] != CABA]
    rows = []
    for loc, prov in pares:
        pid = PROVINCIA_ID.get(prov)
        zprov = PROVINCIA_ZONA.get(pid)
        hit = cache.get(f"{pid}|{loc}") if pid else None
        codigo, metodo = None, "provincia"
        if pid == CABA_ID:
            codigo, metodo = CABA, "departamento"
        elif hit and hit.get("departamento_id") in dz:
            codigo, metodo = dz[hit["departamento_id"]], "departamento"
        elif hit:
            codigo, metodo = nearest_zone(hit["lon"], hit["lat"], sin_caba, zprov), "centroide"
        if codigo is None and pid in centros.index:
            codigo, metodo = nearest_zone(centros.loc[pid, "lon"], centros.loc[pid, "lat"], sin_caba, zprov), "provincia"
        rows.append({"localidad": loc, "provincia": prov, "codigo": codigo, "metodo": metodo if codigo else "sin zona"})
    return pd.DataFrame(rows, columns=["localidad", "provincia", "codigo", "metodo"])


__all__ = ["CABA", "RADIO_GBA_KM", "PROVINCIA_ID", "PROVINCIA_ZONA", "normalize", "province_id", "nearest_zone", "read_georef_departments",
           "department_zones", "province_to_zones", "province_centroids", "locality_zones"]
