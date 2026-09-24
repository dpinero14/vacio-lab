"""Las matrices origen-destino de cargas: 123 zonas, un producto por hoja, en toneladas y en camiones.

Las cuatro ediciones (2012, 2014, 2016 y 2018) vienen como xlsx dentro de un zip,
con un archivo por grupo de producto y una hoja por producto. El formato cambió en
cada edición: encabezados con códigos de zona, con números, o con las dos cosas.
`parse_sheet` no supone ninguno: busca la fila de encabezado por su contenido y
lee lo que hay debajo. Todo devuelve matrices cuadradas indexadas por código de
zona, para que dos ediciones se puedan comparar.
"""

from __future__ import annotations

import io
import json
import re
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

from . import ANIOS, DATA_RAW

CODIGO = re.compile(r"^[A-Z]{3}$")


def zones(raw: Path = DATA_RAW) -> pd.DataFrame:
    """Las zonas de tráfico con su centroide geocodificado: id, codigo, provincia, centroide, lon, lat."""
    # los centroides se geocodificaron una vez (Nominatim, OpenStreetMap, ODbL) y viajan con el paquete;
    # si hay una copia en data/raw, manda esa
    local = raw / "centroides_zonas.json"
    fuente = local if local.exists() else Path(__file__).with_name("centroides_zonas.json")
    c = json.loads(fuente.read_text(encoding="utf-8"))
    df = pd.DataFrame(list(c.values())).sort_values("id").reset_index(drop=True)
    return df[["id", "codigo", "provincia", "centroide", "lon", "lat"]]


def _zip_path(anio: int, raw: Path = DATA_RAW) -> Path:
    return raw / f"mtx-{anio}.zip"


def list_files(anio: int, raw: Path = DATA_RAW) -> list[str]:
    """Las planillas de una edición, con su ruta dentro del zip."""
    with zipfile.ZipFile(_zip_path(anio, raw)) as z:
        # afuera: códigos de zona, resúmenes, aperturas y las planillas de totales por grupo, que repetirían lo ya contado
        return [n for n in z.namelist() if n.lower().endswith((".xlsx", ".xls")) and "odigos" not in n and "esumen" not in n and "pertura" not in n
                and "totales" not in n.lower() and "matriz total" not in n.lower()]


def _is_int(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and float(v).is_integer()


def parse_sheet(rows: list[tuple], zone_codes: list[str]) -> pd.DataFrame:
    """De las celdas crudas de una hoja a una matriz cuadrada codigo x codigo, en la unidad de la hoja.

    Encuentra la fila de encabezado (la primera con muchos códigos de zona o con la
    secuencia 1..n), toma las columnas a partir de ahí y etiqueta cada fila por su
    código si lo trae, o por su número de zona si no.
    """
    n = len(zone_codes)
    id_to_code = {i + 1: c for i, c in enumerate(zone_codes)}
    header_row, first_col, labels = None, None, None
    for r, row in enumerate(rows[:6]):
        cells = list(row)
        codes = [(j, v) for j, v in enumerate(cells) if isinstance(v, str) and CODIGO.match(v.strip())]
        ints = [(j, int(v)) for j, v in enumerate(cells) if _is_int(v)]
        if len(codes) >= n * 0.8:
            header_row, first_col, labels = r, codes[0][0], [v.strip() for _, v in codes]
            break
        if len(ints) >= n * 0.8 and ints[0][1] == 1:
            header_row, first_col, labels = r, ints[0][0], [id_to_code.get(v, str(v)) for _, v in ints]
            break
    if header_row is None:
        raise ValueError("no encontré la fila de encabezado con las zonas")
    data: dict[str, np.ndarray] = {}
    for row in rows[header_row + 1:]:
        cells = list(row)
        label = None
        for v in cells[:first_col]:
            if isinstance(v, str) and CODIGO.match(v.strip()):
                label = v.strip(); break
        if label is None:
            for v in cells[:first_col]:
                if _is_int(v) and int(v) in id_to_code:
                    label = id_to_code[int(v)]; break
        if label is None or label in data:
            continue
        vals = cells[first_col:first_col + len(labels)]
        data[label] = np.array([float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else 0.0 for v in vals] + [0.0] * (len(labels) - len(vals)))
    m = pd.DataFrame.from_dict(data, orient="index", columns=labels)
    return m.reindex(index=zone_codes, columns=zone_codes).fillna(0.0)


def _sheets(anio: int, name: str, raw: Path) -> list[tuple[str, list[tuple]]]:
    """(título, filas) de cada hoja; xlsx con openpyxl, xls viejo con xlrd."""
    with zipfile.ZipFile(_zip_path(anio, raw)) as z:
        data = z.read(name)
    if name.lower().endswith(".xls"):
        import xlrd

        wb = xlrd.open_workbook(file_contents=data)
        return [(ws.name, [tuple(ws.row_values(r)) for r in range(ws.nrows)]) for ws in wb.sheets()]
    import openpyxl

    wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    return [(ws.title, list(ws.iter_rows(values_only=True))) for ws in wb.worksheets]


def read_workbook(anio: int, name: str, zone_codes: list[str], raw: Path = DATA_RAW, unidad: str | None = None) -> dict[str, pd.DataFrame]:
    """Todas las hojas de una planilla como matrices por producto, nombradas sin el sufijo de unidad y año.

    Con `unidad` se filtra por el título de la hoja: en 2012 toneladas y camiones conviven en la misma planilla.
    """
    out = {}
    for titulo, rows in _sheets(anio, name, raw):
        es_camiones = "camion" in titulo.lower()
        if unidad == "camiones" and not es_camiones or unidad == "toneladas" and es_camiones:
            continue
        if len(rows) < 10:
            continue
        try:
            out[clean_name(titulo)] = parse_sheet(rows, zone_codes)
        except ValueError:
            continue
    return out


def clean_name(title: str) -> str:
    """'Arena Silicea Toneladas 2018' -> 'arena silicea'; 'TOTAL CARNES TONELADAS 2016' -> 'total carnes'."""
    t = re.sub(r"\b(toneladas|tonealdas|camiones|ton\.?|tn)\b", " ", title, flags=re.I)
    t = re.sub(r"\b20\d\d\b", " ", t)
    return re.sub(r"\s+", " ", t).strip().lower()


def find_file(anio: int, grupo: str, unidad: str = "toneladas", raw: Path = DATA_RAW) -> str:
    """La planilla de un grupo y una unidad en una edición, por el nombre del archivo."""
    g = grupo.lower().replace("í", "i")
    base = lambda n: n.rsplit("/", 1)[-1].lower().replace("í", "i")   # el nombre del archivo, sin la carpeta del zip
    cands = [n for n in list_files(anio, raw) if g in base(n)]
    if unidad == "camiones":
        cands = [n for n in cands if "camion" in base(n)]
    else:
        cands = [n for n in cands if "camion" not in base(n)]
    if not cands:
        raise FileNotFoundError(f"{anio}: sin planilla de {grupo} en {unidad}")
    return cands[0]


def asymmetry(m: pd.DataFrame) -> pd.DataFrame:
    """Por par ordenado (origen, destino) con carga: ida, vuelta y la fracción que no tiene vuelta.

    `sin_vuelta` = (ida - vuelta) / ida cuando ida > vuelta: 1 es un corredor de un solo
    sentido; 0, un par equilibrado. Cada par aparece una vez, con la ida como el sentido mayor.
    """
    a = m.values
    rows = []
    codes = list(m.index)
    for i in range(len(codes)):
        for j in range(i + 1, len(codes)):
            ida, vuelta = a[i, j], a[j, i]
            if ida == 0 and vuelta == 0:
                continue
            if vuelta > ida:
                i2, j2, ida, vuelta = j, i, vuelta, ida
            else:
                i2, j2 = i, j
            rows.append({"origen": codes[i2], "destino": codes[j2], "ida": ida, "vuelta": vuelta, "sin_vuelta": (ida - vuelta) / ida})
    return pd.DataFrame(rows, columns=["origen", "destino", "ida", "vuelta", "sin_vuelta"]).sort_values("ida", ascending=False).reset_index(drop=True)


def structural_empty(m: pd.DataFrame) -> dict:
    """Resumen de una matriz: total entre zonas, cuánto vuelve emparejado y cuánto es vacío estructural; lo intrazonal aparte."""
    a = m.values.copy()
    intrazonal = float(np.trace(a))
    np.fill_diagonal(a, 0.0)                # lo que no sale de la zona no recorre ningún corredor
    pares = np.minimum(a, a.T)              # lo que tiene vuelta en el mismo par
    total = float(a.sum())
    emparejado = float(pares.sum())
    return {"total": total, "emparejado": emparejado, "vacio_estructural": total - emparejado,
            "pct_sin_vuelta": 100.0 * (total - emparejado) / total if total else float("nan"),
            "intrazonal": intrazonal}


__all__ = ["ANIOS", "zones", "list_files", "parse_sheet", "read_workbook", "clean_name", "find_file", "asymmetry", "structural_empty"]

def all_products(anio: int, zone_codes: list[str], unidad: str = "toneladas", raw: Path = DATA_RAW) -> dict[tuple[str, str], pd.DataFrame]:
    """Todas las matrices de una edición, por (grupo, producto), sin las hojas de totales."""
    out = {}
    archivos = list_files(anio, raw)
    por_archivo = any("camion" in f.rsplit("/", 1)[-1].lower() for f in archivos)   # 2014 a 2018 separan la unidad por planilla; 2012 por hoja
    for f in archivos:
        base = f.rsplit("/", 1)[-1]
        es_camiones = "camion" in base.lower()
        if por_archivo and (unidad == "camiones") != es_camiones:
            continue
        grupo = re.sub(r"^\d+\.?\d*\s*", "", base)
        grupo = re.sub(r"(?i)matrices?|grupo|toneladas|camiones|x producto|\.xlsx?|\b20\d\d\b", " ", grupo)
        grupo = re.sub(r"\s+", " ", grupo).strip().lower()
        for producto, m in read_workbook(anio, f, zone_codes, raw, unidad=None if por_archivo else unidad).items():
            # las hojas de totales del grupo ("total carnes", "matriz combustibles", "matriz total regionales") repetirían los productos
            if producto.startswith(("total", "grupo", "hoja", "matriz")) or "total" in producto:
                continue
            out[(grupo, producto)] = m
    return out


def zone_flows(matrices: dict[tuple[str, str], pd.DataFrame], zonas: list[str], sentido: str = "sale") -> pd.DataFrame:
    """Qué entra o qué sale de un conjunto de zonas, por grupo, producto y contraparte, en la unidad de las matrices.

    `sentido="sale"`: desde las zonas hacia el resto del país; `"entra"`: desde el resto hacia ellas.
    Lo que se mueve entre las zonas del conjunto queda afuera: no es un corredor con el resto.
    """
    rows = []
    for (grupo, producto), m in matrices.items():
        otras = [c for c in m.index if c not in zonas]
        bloque = m.loc[zonas, otras].sum(axis=0) if sentido == "sale" else m.loc[otras, zonas].sum(axis=1)
        for z, v in bloque[bloque > 0].items():
            rows.append({"grupo": grupo, "producto": producto, "contraparte": z, "t": float(v)})
    return pd.DataFrame(rows, columns=["grupo", "producto", "contraparte", "t"]).sort_values("t", ascending=False).reset_index(drop=True)


__all__ += ["all_products", "zone_flows"]

