# Información técnica de Pack AI 2.4.0

## Métricas del código

Las métricas se calcularon con `PackService.preview` sobre el propio proyecto y su política normal de exclusión.

| Lenguaje | Archivos | Líneas físicas no vacías |
|---|---:|---:|
| Python | 28 | 1,865 |
| CSS | 1 | 180 |
| PowerShell | 2 | 87 |
| TOML | 1 | 61 |
| JavaScript | 1 | 31 |
| YAML | 1 | 25 |
| HTML | 1 | 16 |
| **Total** | **35** | **2,265** |

El conteo incluye comentarios y configuraciones declarativas reconocidas, excluye líneas vacías y no considera Markdown o texto general como código. No se presenta como SLOC lógico porque no usa parsers específicos por lenguaje.

## Cambios técnicos de la versión 2.4.0

- `PackMetrics.code_files`: cantidad de archivos fuente reconocidos.
- `PackMetrics.code_lines`: total de líneas físicas no vacías.
- `PackMetrics.language_code_lines`: desglose ordenado por lenguaje.
- CLI, GUI y API usan la misma métrica calculada desde los bytes exactos del plan de archivo.
- Detección por extensión, nombres convencionales y shebang.
- Compatibilidad preservada mediante valores predeterminados en los nuevos campos públicos.

## Robustez del ZIP

El escritor final usa:

- `ZIP_DEFLATED` con nivel 9;
- ZIP64 habilitado;
- archivo temporal en el mismo sistema de archivos que el destino;
- lectura integral mediante `testzip()`;
- rechazo de miembros duplicados, faltantes, inesperados o fuera de orden;
- verificación de método de compresión, tamaño, CRC y bytes de cada miembro;
- `os.replace` únicamente después de una verificación satisfactoria;
- eliminación del temporal y conservación de la salida anterior ante cualquier fallo.

## Validación ejecutada

- Ruff format: sin cambios pendientes.
- Ruff check: sin incidencias.
- mypy estricto: sin errores en 25 módulos.
- Pytest: 84 pruebas aprobadas.
- Cobertura: 79.68%, superior al umbral de 70%.
- JavaScript de la GUI: comprobación sintáctica con `node --check`.
- Paquete: sdist y wheel 2.4.0 construidos correctamente; los artefactos de build no se incluyen en este ZIP fuente.

## Corrección de estabilidad del viewport de la GUI

Se corrigió el desplazamiento irreversible de toda la interfaz al alternar opciones que cambian mucho el contenido de la preview, especialmente `Incluir lockfiles`.

La causa era un checkbox transparente con posicionamiento absoluto sin contenedor relativo. Al conservar el foco mientras cambiaba la altura del panel lateral, WebView2 desplazaba el documento principal para revelar el control invisible. Como el scroll del documento estaba oculto, la barra superior quedaba fuera de la ventana y no existía una acción de usuario capaz de restaurarla.

La solución contiene el input dentro de su interruptor, fija `#root` al viewport, asigna áreas explícitas al layout principal y mantiene visible el control activo dentro del panel lateral. Se conserva un guard de recuperación para scroll, foco, resize y `visualViewport`.

Validación específica:

- 97 pruebas Python aprobadas;
- Ruff format/check y mypy estricto correctos;
- sintaxis de `app.js` validada con Node;
- smoke test automatizado en Chromium alternando lockfiles con un crecimiento grande de métricas;
- viewport probado en 980×640, 1360×860, 1568×963 y 1920×1080, siempre con `scrollY = 0`, barra superior en `y = 0` y dock pegado al borde inferior.
