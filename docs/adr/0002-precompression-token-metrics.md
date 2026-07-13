# ADR 0002: métricas sobre una instantánea previa a la compresión

## Estado

Aceptado

## Contexto

El CLI debe informar archivos incluidos, archivos textuales y binarios, tamaño sin comprimir, tamaño final del ZIP, tokens estimados y los archivos con mayor aporte de tokens. Una futura GUI también necesita previsualizar estas métricas sin crear un ZIP en cada cambio de configuración.

Calcular únicamente después de abrir el ZIP garantiza correspondencia, pero obliga a comprimir para cada preview. Calcular sobre rutas y volver a leerlas al comprimir introduce una condición de carrera: un archivo puede cambiar entre ambas operaciones y hacer que el reporte no describa el ZIP real.

Los proyectos objetivo normalmente no superan 100 MB.

## Decisión

Cada operación construye un `ArchivePlan` efímero con los bytes exactos de todos los miembros permitidos. Ese plan:

1. aplica exclusiones, clasificación y escaneo de secretos;
2. conserva los bytes originales sin recodificarlos;
3. alimenta `ArchiveMetricsAnalyzer` antes de comprimir;
4. alimenta el writer del ZIP con los mismos bytes;
5. se descarta al terminar y nunca se persiste.

`PackService.preview` crea y analiza el plan sin escribir un ZIP. `PackService.pack` vuelve a construir una instantánea actual, calcula las métricas, escribe esos mismos bytes de forma atómica y completa `zip_size` a partir del archivo final.

El conteo principal usa `tiktoken` con `o200k_base`. Si la dependencia o el tokenizador fallan, se degrada por archivo a `ceil(bytes_utf8 / 4)` y el contrato marca `degraded=True`.

Las imágenes raster y los PDF se incluyen como binarios únicamente si su firma coincide con una lista permitida. No aportan tokens. Ejecutables, binarios desconocidos y formatos pesados ya excluidos permanecen fuera del ZIP.

## Consecuencias

Positivas:

- Las métricas de un pack corresponden exactamente a sus bytes sin releer el ZIP.
- La GUI puede previsualizar tokens y tamaño sin comprimir sin ejecutar compresión.
- El contenido archivado nunca cambia por decodificación o tokenización.
- Un fallo de métricas no invalida la creación del ZIP.
- El tokenizador puede sustituirse mediante `TokenEstimator`.

Negativas:

- La operación conserva temporalmente en memoria el contenido incluido completo.
- Una preview es una instantánea; si el proyecto cambia antes del pack, la siguiente operación puede producir métricas distintas.
- El tamaño comprimido solo puede conocerse después de crear el ZIP.
- PDF e imágenes no se inspeccionan internamente para detectar secretos.

## Alternativas consideradas

- Analizar el ZIP terminado: descartado para preview por requerir compresión.
- Leer archivos para métricas y volver a leerlos para escribir: descartado por inconsistencias ante cambios concurrentes.
- Estimar el tamaño comprimido: descartado porque depende del contenido, metadatos y algoritmo y sería engañoso.
