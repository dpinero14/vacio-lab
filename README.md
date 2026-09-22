# vacio-lab

El mapa del vacío: cuánto del transporte de cargas argentino vuelve sin carga,
tramo por tramo y producto por producto, con las matrices origen-destino de la
Secretaría de Transporte. Octavo repo de la serie Sur Analytics y el segundo de
logística, después de la ruta de la arena.

> En 2018, el 43 % de los camiones-kilómetro de las rutas argentinas se hicieron
> en un sentido que no tiene carga de vuelta. No es un problema de información:
> es la forma de la economía. Este repo lo mide con los datos oficiales y muestra
> dónde está, cuánto es y qué cargas podrían emparejarse.

*Trabajo en curso: 22 de septiembre de 2026.*

## Qué hace

| Notebook | Qué hace |
|---|---|
| `01_el_mapa_del_vacio` | Lee las matrices origen-destino de 2012 a 2018 (123 zonas, 113 productos, en toneladas y en camiones) y la red vial con el flujo de camiones por sentido. Mide el vacío estructural por par de zonas, por producto y por tramo de ruta. Toma la arena de fractura como caso extremo y busca qué podría volver cargado desde Neuquén. Dibuja el mapa. |

## Datos

Todo abierto y verificado el 22 de septiembre de 2026: ver `data/README.md`.
`python scripts/download_data.py` baja unos 215 MB a `data/raw/`.

## Cómo correrlo

```
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe scripts/download_data.py
.venv\Scripts\python.exe -m pytest -q tests
```

## Autor

Diego Piñero, Sur Analytics. Código con licencia MIT.
