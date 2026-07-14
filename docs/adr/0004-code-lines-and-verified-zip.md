# ADR 0004: LOC físico y verificación integral del ZIP

## Estado

Aceptado para Pack AI 2.4.

## Contexto

El reporte existente informaba archivos, bytes y tokens, pero no permitía estimar rápidamente el volumen de código ni su distribución técnica. Al mismo tiempo, el escritor era atómico, aunque no releía el temporal completo antes de sustituir una salida existente.

## Decisión sobre líneas de código

`ArchiveMetricsAnalyzer` detecta lenguajes por extensión, nombres convencionales y shebang. Para cada archivo reconocido cuenta líneas físicas no vacías:

- los comentarios cuentan;
- las líneas en blanco no cuentan;
- Markdown y texto general no cuentan;
- configuraciones declarativas reconocidas, como JSON, TOML, YAML, Terraform o Dockerfile, sí cuentan;
- el cálculo usa la misma vista decodificada de los bytes exactos que se escribirán, sin recodificar el archivo.

El contrato público expone `code_files`, `code_lines` y `language_code_lines`. CLI, GUI y API consumen esos campos sin recalcularlos. La métrica no se denomina SLOC lógico porque no analiza sintaxis ni elimina comentarios mediante parsers específicos.

## Decisión sobre robustez del ZIP

El temporal se escribe con `ZIP_DEFLATED`, nivel 9, ZIP64 habilitado y timestamps tolerantes. Antes del reemplazo atómico:

1. se abre nuevamente el ZIP;
2. `testzip()` lee todos los miembros y valida CRC;
3. se rechazan miembros duplicados, faltantes o inesperados;
4. se exige DEFLATE y se comparan orden, tamaño, CRC y bytes de cada miembro con el `ArchivePlan`;
5. solo después se ejecuta `os.replace`.

Un fallo de escritura o verificación elimina el temporal y conserva intacta cualquier salida anterior.

## Consecuencias

- La previsualización y el empaquetado ofrecen el mismo LOC para una instantánea idéntica.
- El desglose es determinista y extensible, pero depende de una tabla explícita de lenguajes.
- La verificación añade una lectura completa del temporal; el costo es deliberado para detectar corrupción antes de publicar el artefacto.
- DEFLATE nivel 9 prioriza tamaño y portabilidad sobre velocidad máxima.
