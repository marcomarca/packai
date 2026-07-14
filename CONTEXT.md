# Contexto de dominio

## Propósito

Pack AI transforma el contenido permitido de una carpeta en un ZIP revisable por una IA, minimizando archivos irrelevantes y filtraciones accidentales, y reportando el costo textual aproximado del artefacto.

## Glosario

| Término | Significado |
|---|---|
| Raíz | Carpeta del proyecto que se recorre. |
| Miembro | Ruta relativa almacenada dentro del ZIP. |
| Instantánea | Bytes efímeros e inmutables seleccionados para preview o pack. |
| Archivo textual | Miembro decodificable de forma segura que aporta tokens. |
| Activo binario | Imagen raster o PDF reconocido; aporta tamaño, no tokens. |
| Exclusión estricta | Ruta que nunca se incluye, incluso con `force`. |
| Lockfile | Archivo reproducible de resolución de dependencias, incluido por defecto y retirable como grupo. |
| Ruta sensible | Archivo excluido por nombre salvo que `force` lo permita. |
| Hallazgo | Detección enmascarada asociada a un archivo o al contexto Git. |
| Contexto Git | Markdown derivado exclusivamente del último commit confirmado. |
| Preview | Análisis precompresión que no crea ZIP y no conoce su tamaño final. |
| TokenEstimator | Puerto sustituible que calcula tokens de un texto. |
| Estimación degradada | Fallback `bytes UTF-8 / 4` usado cuando falla el tokenizador principal. |

## Invariantes

1. Ningún miembro del ZIP usa una ruta absoluta.
2. Los enlaces simbólicos no se siguen ni se incluyen.
3. `.env` y sus variantes reales nunca se incluyen.
4. Un secreto reportado nunca se devuelve completo.
5. La salida anterior no se reemplaza hasta que el ZIP nuevo se cierre correctamente.
6. La capa de aplicación no imprime ni depende de una tecnología de interfaz.
7. Las exclusiones del usuario deben permanecer dentro de la raíz.
8. El contexto Git representa `HEAD`; no mezcla cambios sin commit.
9. Métricas y ZIP de una misma operación usan exactamente los mismos bytes.
10. El análisis nunca recodifica ni modifica el contenido archivado.
11. Los activos binarios permitidos no aportan tokens.
12. Un fallo de métricas no invalida un ZIP correctamente creado.
13. Los lockfiles conocidos se incluyen por defecto y un único cambio de opción debe excluirlos en CLI, GUI y API.

## Flujo de preview

1. El front end crea `PackRequest`.
2. `PackService.preview` valida y compone políticas.
3. `ArchiveService` construye una instantánea efímera.
4. `ArchiveMetricsAnalyzer` calcula conteos, tamaño y tokens.
5. Se devuelve `PackPreview`; no se crea ningún archivo.

## Flujo de pack

1. Se construye una instantánea actual.
2. Se calculan métricas precompresión.
3. Se escriben esos mismos bytes en un ZIP temporal.
4. Se reemplaza atómicamente el destino.
5. Se incorpora el tamaño físico final y se devuelve `PackResult`.
