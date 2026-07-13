# Contexto de dominio

## Propósito

Pack AI transforma el contenido permitido de una carpeta de proyecto en un ZIP revisable por una IA, minimizando archivos irrelevantes y filtraciones accidentales de secretos.

## Glosario

| Término | Significado |
|---|---|
| Raíz | Carpeta del proyecto que se recorre. |
| Miembro | Ruta relativa almacenada dentro del ZIP. |
| Exclusión estricta | Ruta que nunca se incluye, incluso con `force`. |
| Ruta sensible | Archivo excluido por nombre salvo que `force` lo permita. |
| Hallazgo | Detección enmascarada asociada a un archivo o al contexto Git. |
| Contexto Git | Markdown derivado exclusivamente del último commit confirmado. |
| Front end | CLI, GUI, API u otra capa que presenta el caso de uso. |
| Proveedor Git | Implementación del puerto `GitContextProvider`. |

## Invariantes

1. Ningún miembro del ZIP usa una ruta absoluta.
2. Los enlaces simbólicos no se siguen ni se incluyen.
3. `.env` y sus variantes reales nunca se incluyen.
4. Un secreto reportado nunca se devuelve completo; solo su valor enmascarado.
5. La salida anterior no se reemplaza hasta que el ZIP nuevo se cierre correctamente.
6. La capa de aplicación no imprime ni depende de una tecnología de interfaz.
7. Las exclusiones proporcionadas por el usuario deben existir y permanecer dentro de la raíz.
8. El contexto Git representa `HEAD`; no mezcla cambios sin commit.

## Flujo principal

1. El front end crea `PackRequest`.
2. `PackService` valida y normaliza exclusiones.
3. Se compone la política predeterminada, la configuración del proyecto y las exclusiones de la petición.
4. `ArchiveService` recorre archivos, aplica políticas y escanea contenido.
5. Opcionalmente consulta `GitContextProvider`.
6. Escribe un ZIP temporal y lo reemplaza atómicamente.
7. Devuelve `PackResult` y emite `ProgressEvent` durante el proceso.
