# Pack AI

Pack AI empaqueta un proyecto en un ZIP orientado a revisión por herramientas de IA. Excluye rutas irrelevantes, ejecutables, binarios desconocidos y secretos detectables; puede agregar el contexto del último commit y reporta el tamaño y los tokens estimados del contenido enviado.

## Arquitectura

El proyecto ofrece dos superficies:

- `packai`: API estable y neutral respecto de la interfaz. Es la base para CLI, GUI, API HTTP u otras integraciones.
- `pack_ai.py`: fachada de compatibilidad para imports y ejecución usados por versiones 1.x.

La lógica de empaquetado no imprime, no accede al portapapeles y no depende de `argparse`. `PackService.preview` calcula una instantánea sin comprimir; `PackService.pack` analiza y escribe exactamente los mismos bytes, y devuelve contratos inmutables aptos para una futura GUI.

## Requisitos

- Python 3.12 o superior.
- `pyenv` para fijar el intérprete.
- `uv` para dependencias, entorno y lockfile.
- `tiktoken` para el conteo principal con `o200k_base`.
- Git, opcional, para nombrado y contexto del último commit.
- PowerShell o `pwsh`, solo para funciones de portapapeles.

Este paquete no incluye `uv.lock`. Después de integrar los cambios en un repositorio con lockfile propio:

```bash
pyenv install -s 3.12.10
pyenv local 3.12.10
uv lock
uv sync --locked
uv run packai --version
```

## Uso por CLI

```bash
# Empaquetar la carpeta actual
packai

# Empaquetar sin usar el portapapeles
packai C:\Ruta\Proyecto --copy none

# Mostrar los 10 archivos con más tokens
packai . --token-top 10

# Ocultar el ranking, conservando el total
packai . --token-top 0

# Elegir salida y exclusiones relativas repetibles
packai . --output ..\proyecto.zip -e datos -e cache/tmp --copy none

# Agregar el diff del último commit confirmado
packai . -g
```

Salida de referencia:

```text
Archivos incluidos:             284
Archivos de texto:              251
Archivos binarios:               33
Tamaño sin comprimir:         4.8 MB
Tamaño del ZIP:              1.2 MB
Tokens estimados:          612,430

Archivos con más tokens:
  src/generated/client.ts       184,220
  package-lock.json             102,845
  docs/api-reference.md          48,102
```

Si `tiktoken` no puede cargarse, el ZIP se crea igualmente y el CLI marca una estimación degradada basada en bytes UTF-8.

### Opciones

| Opción | Descripción |
|---|---|
| `--version`, `-v` | Muestra la versión. |
| `--copy file\|path\|none` | Copia el ZIP, su ruta o nada. |
| `--output RUTA` | Define el ZIP de salida. |
| `--force`, `-f` | Incluye archivos con alertas, excepto `.env` y ejecutables/binarios no permitidos. |
| `--exclude`, `--exclude-path`, `-e`, `-E`, `-I` | Excluye una carpeta relativa existente; repetible. |
| `--token-top N` | Cantidad de archivos con más tokens; `0` oculta el ranking. |
| `--commit-clipboard`, `-c` | Copia el Markdown del último commit sin crear ZIP. |
| `-g` | Incluye `git--diff_last_commit.md` y sus tokens. |
| `--no-env-example` | Excluye `.env.example`, `.env.sample` y `.env.template`. |

## Texto, imágenes, PDF y ejecutables

- El texto aporta cantidad de archivos, bytes y tokens.
- PNG, JPEG, GIF, WebP, BMP, TIFF, ICO, AVIF, HEIC/HEIF y PDF se incluyen por defecto solo cuando su firma coincide con el formato esperado.
- Esos activos cuentan como binarios y aportan tamaño, pero no tokens.
- Ejecutables, binarios desconocidos, multimedia y artefactos de compilación permanecen excluidos.
- Cualquier imagen o PDF puede excluirse mediante `.ignore2packai`, `extra_ignore_patterns` o una exclusión aplicable.
- SVG continúa tratándose como texto porque puede contener código, scripts y secretos.

El análisis nunca recodifica el contenido: el ZIP recibe los bytes originales.

## API para futuras interfaces

### Preview sin crear ZIP

```python
from pathlib import Path

from packai import PackRequest, PackService

request = PackRequest(
    root=Path("mi-proyecto"),
    output_zip=Path("mi-proyecto.zip"),
    include_git_context=True,
    token_top=10,
)

preview = PackService().preview(request)
print(preview.metrics)
assert not request.output_zip.exists()
```

`preview.metrics.zip_size` es `None`; el resto describe la instantánea precompresión.

### Creación final

```python
result = PackService().pack(request)

if result.metrics is not None:
    print(result.metrics.estimated_tokens)
    print(result.metrics.zip_size)
    print(result.metrics.largest_token_files)
```

Contratos públicos relevantes:

- `PackRequest`: configuración, exclusiones y `token_top`.
- `PackPreview`: resultado precompresión sin artefacto físico.
- `PackResult`: resultado final y ruta del ZIP.
- `PackMetrics` y `FileTokenMetrics`: métricas neutrales respecto de UI.
- `TokenEstimator`: puerto sustituible para otro encoding o proveedor.
- `ProgressEvent`: eventos para árbol, barra, log o telemetría.
- `GitContextProvider`: puerto sustituible para Git.

Un fallo total del análisis deja `metrics=None`, emite una advertencia y no invalida el ZIP.

## Seguridad y consistencia

- `.env`, `.env.*` y variantes reales se excluyen incluso con `--force`.
- Los hallazgos se enmascaran antes de formar parte de resultados.
- Los enlaces simbólicos no se siguen.
- Las firmas ejecutables se bloquean incluso si el archivo usa una extensión de imagen.
- El ZIP se construye en un temporal y reemplaza la salida únicamente después de cerrarse correctamente.
- PDF e imágenes no se inspeccionan internamente para secretos; deben revisarse antes de compartir.
- La detección por regex reduce riesgo, pero no garantiza ausencia de secretos.

## Calidad

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy src/packai
uv run pytest
uv run pytest --cov=packai --cov-fail-under=70
```

Decisiones y contratos:

- `docs/architecture.md`
- `docs/testing-strategy.md`
- `docs/adr/0001-stable-application-contracts.md`
- `docs/adr/0002-precompression-token-metrics.md`
- `CONTEXT.md`
- `AI_SKILLS.md`
