"""Baja a data/raw todo lo que usa el repo: las matrices origen-destino 2012 a 2018, las zonas y la red vial con flujos por sentido.

Fuente: Secretaría de Transporte, dataset "Matriz Origen-Destino vial de Transporte de Cargas"
(datos.transporte.gob.ar/dataset/matriz-od-vial-cargas) y su IDE (ide.transporte.gob.ar/geoserver, WFS).
Unos 215 MB en total. Se puede correr varias veces: lo que ya está, no se vuelve a bajar.
"""

import sys
from pathlib import Path
from urllib.parse import quote

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from vlab import DATA_RAW  # noqa: E402

CKAN = "https://datos.transporte.gob.ar/dataset/3869ea48-0c3f-4f17-b46b-5919e1815f30/resource"
WFS = "https://ide.transporte.gob.ar/geoserver/idera/ows"

ARCHIVOS = {
    "mtx-2018.zip": f"{CKAN}/202252ea-8741-4e0d-9981-3026ab611a99/download/mtx-2018.zip",
    "mtx-2016.zip": f"{CKAN}/e8089792-b609-4c7b-9fd4-d6c9fda8ead2/download/2016.zip",
    "mtx-2014.zip": f"{CKAN}/9cc2160e-55e1-441f-a000-c5a0ce3b06f0/download/2014.zip",
    "mtx-2012.zip": f"{CKAN}/6d0052f6-c1a9-4076-9608-9dd8605bde49/download/2012.zip",
    "codigos_zonas.xls": f"{CKAN}/1d2cf181-89fc-4ba1-9803-2508b47ec1a3/download/03.-codigos-de-zonas.xls",
    "zonificacion.jpg": f"{CKAN}/e30513f7-65b0-453c-b42c-d431063f3153/download/02.-zonificacion.jpg",
    "metodologia_od_2018.pdf": f"{CKAN}/6457df85-bf46-40dc-8fea-c8904608fb5e/download/informe_metodologico_matrices_origen_y_destino_de_cargas_2018_final.pdf",
}
# capas de la red vial simplificada con la asignación de camiones 2018, una por grupo y el total
CAPAS = {
    "red_total_2018.geojson": "idera:Carga transportada total 2018",
    "red_grupo_carnes_2018.geojson": "idera:Carga transportada grupo carnes 2018",
    "red_grupo_ganado_en_pie_2018.geojson": "idera:Carga transportada grupo  ganado en pie2018",
    "red_grupo_combustibles_2018.geojson": "idera:Carga transportada grupo combustibles 2018",
    "red_grupo_granos_2018.geojson": "idera:Carga transportada grupo granos 2018",
    "red_grupo_industrializados_2018.geojson": "idera:Carga transportada grupo industrializados 2018",
    "red_grupo_mineria_2018.geojson": "idera:Carga transportada grupo mineria 2018",
    "red_grupo_regionales_2018.geojson": "idera:Carga transportada grupo regionales 2018",
    "red_semiterminados_2018.geojson": "idera:Carga transportada semiterminados 2018",
}


def bajar(url: str, destino: Path, timeout: int = 600) -> None:
    if destino.exists() and destino.stat().st_size > 0:
        print(f"  ya está: {destino.name}")
        return
    r = requests.get(url, timeout=timeout, headers={"User-Agent": "vacio-lab/0.1 (+https://github.com/dpinero14)"})
    r.raise_for_status()
    destino.write_bytes(r.content)
    print(f"  {destino.name}: {len(r.content) / 1e6:.1f} MB")


def main() -> None:
    DATA_RAW.mkdir(parents=True, exist_ok=True)
    print("matrices y zonas:")
    for nombre, url in ARCHIVOS.items():
        bajar(url, DATA_RAW / nombre)
    print("red vial con flujos por sentido:")
    for nombre, capa in CAPAS.items():
        bajar(f"{WFS}?service=WFS&version=1.0.0&request=GetFeature&typeName={quote(capa)}&outputFormat=application/json", DATA_RAW / nombre)
    print("listo")


if __name__ == "__main__":
    main()
