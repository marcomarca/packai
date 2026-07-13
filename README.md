# Pack AI

Pack AI empaqueta un proyecto en un ZIP orientado a revisión por herramientas de IA. Excluye rutas irrelevantes, ejecutables, binarios desconocidos y secretos detectables; puede agregar el contexto del último commit y reporta tamaño, archivos y tokens estimados.

## Arquitectura

El proyecto ofrece tres superficies sobre el mismo núcleo:

- CLI tradicional mediante `packai .`.
- GUI local mediante `packai gui .`.
- API Python mediante `PackService.preview` y `PackService.pack`.

`pack_ai.py` conserva la fachada de compatibilidad usada por versiones 1.x. La lógica de empaquetado no depende de `argparse`, PyWebView, React ni el portapapeles. CLI y GUI traducen sus opciones al mismo `PackRequest`.

## Requisitos

- Python 3.12 o superior.
- `pyenv` para fijar el intérprete.
- `uv` para dependencias, entorno y lockfile.
- Git, opcional, para nombrado y contexto del último commit.
- PowerShell o `pwsh`, solo para las funciones de portapapeles.
- Para la GUI: PyWebView y watchdog mediante el extra opcional `gui`; en Linux ese extra instala además el backend Qt.

El vocabulario `o200k_base` se distribuye dentro del paquete y se verifica mediante SHA-256. El conteo preciso no necesita red ni una caché previa de `tiktoken`.

Este paquete no incluye `uv.lock`. Después de integrar los cambios en un repositorio con lockfile propio:

```bash
pyenv install -s 3.12.10
pyenv local 3.12.10
uv lock
uv sync --locked --extra gui
uv run packai --version
```

Para instalar solo el CLI:

```bash
uv sync --locked
```

## Interfaz gráfica

```bash
# Abrir la carpeta actual
uv run packai gui .

# Abrir otra carpeta con configuración inicial
uv run packai gui C:\Ruta\Proyecto -e generated -e cache --force -g --token-top 10
```

La GUI incluye:

- árbol jerárquico exclusivo de carpetas;
- casillas seleccionadas, desmarcadas e indeterminadas;
- carpetas bloqueadas visibles pero deshabilitadas;
- métricas reactivas de tokens, tamaño, texto, binarios y ranking;
- opciones `Force`, contexto Git, `.env.example`, ranking y portapapeles;
- reescaneo por eventos con debounce y sondeo de baja frecuencia como fallback;
- reescaneo obligatorio antes de cada generación;
- comandos reproducibles para empaquetar directamente o reabrir la selección;
- botón para generar de nuevo el ZIP con el estado actual del proyecto.

La selección existe solo mientras la ventana está abierta. La GUI no crea configuración local ni permite cambiar la ruta de salida. El ZIP usa el mismo nombre automático que el CLI.

### Fallos de instalación o backend gráfico

Si PyWebView no está instalado, `packai gui` muestra los comandos necesarios sin afectar al CLI:

```bash
uv lock
uv sync --locked --extra gui
uv run packai gui .
```

En Windows, si las dependencias están instaladas pero la ventana no abre, ejecuta `winget install -e --id Microsoft.EdgeWebView2Runtime`; si `winget` falla, instala o repara **Microsoft Edge WebView2 Evergreen Runtime** desde Microsoft. En Linux, el extra `gui` instala el backend Qt y requiere una sesión gráfica X11 o Wayland activa. El mensaje de error conserva siempre el comando CLI tradicional como alternativa.

## Uso por CLI

```bash
# Empaquetar la carpeta actual
uv run packai .

# Empaquetar sin usar el portapapeles
uv run packai C:\Ruta\Proyecto --copy none

# Mostrar los 10 archivos con más tokens
uv run packai . --token-top 10

# Ocultar el ranking, conservando el total
uv run packai . --token-top 0

# Elegir salida y exclusiones relativas repetibles
uv run packai . --output ..\proyecto.zip -e datos -e cache/tmp --copy none

# Agregar el diff del último commit confirmado
uv run packai . -g
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

Si `tiktoken` o el vocabulario local no pueden cargarse, el ZIP se crea igualmente y la salida marca una estimación degradada basada en bytes UTF-8.

### Opciones compartidas relevantes

| Opción | Descripción |
|---|---|
| `--copy file\|path\|none` | Copia el ZIP, su ruta o nada. |
| `--force`, `-f` | Incluye archivos con alertas, excepto `.env` y ejecutables/binarios no permitidos. |
| `--exclude`, `--exclude-path`, `-e`, `-E`, `-I` | Excluye una carpeta relativa existente; repetible. |
| `--token-top N` | Cantidad de archivos con más tokens; `0` oculta el ranking. |
| `-g` | Incluye `git--diff_last_commit.md` y sus tokens. |
| `--no-env-example` | Excluye `.env.example`, `.env.sample` y `.env.template`. |

El CLI tradicional también admite `--output` y `--commit-clipboard`. La GUI no permite cambiar la salida y no ofrece el modo exclusivo de copiar contexto Git.

## Texto, imágenes, PDF y ejecutables

- El texto aporta cantidad de archivos, bytes y tokens.
- PNG, JPEG, GIF, WebP, BMP, TIFF, ICO, AVIF, HEIC/HEIF y PDF se incluyen por defecto solo cuando su firma coincide con el formato esperado.
- Esos activos cuentan como binarios y aportan tamaño, pero no tokens.
- Ejecutables, binarios desconocidos, multimedia y artefactos de compilación permanecen excluidos.
- Cualquier imagen o PDF puede excluirse mediante `.ignore2packai`, `extra_ignore_patterns` o una exclusión aplicable.
- SVG continúa tratándose como texto porque puede contener código, scripts y secretos.

El análisis nunca recodifica el contenido: el ZIP recibe los bytes originales.

## API Python

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

result = PackService().pack(request)
if result.metrics is not None:
    print(result.metrics.estimated_tokens)
    print(result.metrics.zip_size)
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
- Las firmas ejecutables se bloquean aunque el archivo use una extensión de imagen.
- El ZIP se construye en un temporal y reemplaza la salida solo después de cerrarse correctamente.
- PDF e imágenes no se inspeccionan internamente para secretos; deben revisarse antes de compartir.
- La detección por regex reduce riesgo, pero no garantiza ausencia de secretos.
- Los recursos HTML, CSS, JavaScript y React de la GUI son locales; no existe CDN ni servidor HTTP.

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
- `docs/adr/0003-local-pywebview-gui.md`
- `CONTEXT.md`
- `AI_SKILLS.md`
