# Panel de flotas: una semana de tu flota

La única forma directa de medir el vacío es preguntarle al camión. En el
Reino Unido la estadística oficial sale de eso: cada semana se sortean
vehículos del registro y el operador anota sus viajes de esa semana, cargado o
vacío (encuesta CSRGT). Argentina no la tiene. Este panel es la versión
mínima y voluntaria: una flota aporta los viajes de sus vehículos durante una
semana, y el repo devuelve el vacío por equipo y por ruta, publicado solo
cuando hay al menos tres flotas detrás de cada número.

## Cómo aportar

1. Bajar `plantilla_semana_flota.csv` y completarla con **todos** los viajes
   de la semana de cada vehículo que se quiera incluir (los vacíos también:
   son el dato).
2. Una fila por viaje. Columnas:

| Columna | Qué va |
|---|---|
| `flota` | Un nombre corto de la flota. Puede ser un seudónimo: no se publica. |
| `vehiculo` | Identificador interno del vehículo (no la patente). |
| `equipo` | `tolva`, `batea`, `cisterna`, `jaula`, `frio`, `general`, `contenedor` u `otro`. |
| `fecha` | Día del viaje, `AAAA-MM-DD`. |
| `origen`, `destino` | Localidades. |
| `ruta` | La ruta principal del viaje (`RN 9`, `RN 152`, `RP 65`...). |
| `km` | Kilómetros del viaje. |
| `cargado` | `1` si iba con carga, `0` si iba vacío. |
| `producto` | Qué llevaba, si iba cargado. |
| `toneladas` | Cuánto, si se sabe. |

3. Mandar el archivo por el formulario o por correo (el enlace está en la
   página del repo). No hace falta que la semana sea "típica": el panel
   promedia.

## Qué se publica y qué no

- Se publica el vacío (kilómetros vacíos sobre kilómetros totales) por equipo
  y por ruta, con el número de flotas, vehículos y viajes detrás.
- Ninguna celda se publica con menos de tres flotas. Ninguna flota se
  identifica. Cada flota recibe su propio resumen, que es suyo.
- El archivo original no se versiona en el repo (queda en `data/raw/panel/`,
  que está fuera de git).

## Cómo se procesa

`src/vlab/panel.py`: `read_panel` valida la planilla, `empty_share` calcula
el vacío por las columnas que se pidan, `publishable` aplica la regla de las
tres flotas y `week_report` arma el informe de la semana. Los tests usan una
planilla sintética de tres flotas.

## El formulario

Para quien no quiera manejar un CSV, las mismas columnas caben en un
formulario de una pantalla por viaje. Las preguntas, en el mismo orden que la
planilla: nombre corto de la flota, identificador del vehículo, tipo de
equipo (lista), fecha, origen, destino, ruta principal, kilómetros, ¿iba
cargado? (sí/no), producto, toneladas. La exportación del formulario se lee
con `read_panel` sin cambios si las columnas llevan esos nombres.
