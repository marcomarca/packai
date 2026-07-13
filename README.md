# Pack AI

Pack AI empaqueta un proyecto en un ZIP orientado a revisión por herramientas de IA. Excluye archivos pesados, rutas configuradas y secretos detectables; también puede agregar el contexto del último commit confirmado.

## Estado de arquitectura

Desde la versión 2.0 el proyecto tiene dos superficies deliberadamente separadas:

- `packai`: API estable y neutral respecto de la interfaz. Es la base para CLI, GUI, API HTTP u otras integraciones.
- `pack_ai.py`: fachada de compatibilidad para imports y ejecución usados por versiones 1.x.

La lógica de empaquetado no imprime, no accede al portapapeles y no depende de `argparse`. Esas responsabilidades viven en adaptadores externos. El resultado se devuelve mediante contratos inmutables y el progreso se comunica mediante eventos tipados.

## Requisitos

- Python 3.12 o superior.
- `pyenv` para fijar el intérprete del proyecto.
- `uv` para entorno, dependencias, lockfile y ejecución.
- Git, opcional, para nombrado y contexto del último commit.
- PowerShell o `pwsh`, solo para las funciones de portapapeles.

## Instalación de desarrollo

```bash
pyenv install -s 3.12.10
pyenv local 3.12.10
uv sync --locked
uv run packai --version
```

En Windows se puede instalar el comando global del proyecto:

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

El instalador sincroniza el lockfile y crea `%USERPROFILE%\bin\packai.cmd`. Para retirarlo:

```powershell
powershell -ExecutionPolicy Bypass -File .\uninstall.ps1
```

## Uso por CLI

```bash
# Empaquetar la carpeta actual
packai

# Empaquetar una ruta específica sin usar el portapapeles
packai C:\Ruta\Proyecto --copy none

# Elegir salida
packai . --output ..\proyecto.zip --copy none

# Excluir carpetas relativas a la raíz; la opción es repetible
packai . -e datos -e cache/tmp

# Agregar el diff del último commit confirmado
packai . -g

# Copiar únicamente el contexto del último commit
packai . -c

# Forzar inclusiones con alertas permitidas; los .env reales siguen bloqueados
packai . -gf
```

### Opciones

| Opción | Descripción |
|---|---|
| `--version`, `-v` | Muestra la versión. |
| `--copy file\|path\|none` | Copia el ZIP, su ruta o nada. |
| `--output RUTA` | Define el ZIP de salida. |
| `--force`, `-f` | Incluye archivos con alertas, excepto `.env` y variantes reales. |
| `--exclude`, `--exclude-path`, `-e`, `-E`, `-I` | Excluye una carpeta relativa existente; repetible. |
| `--commit-clipboard`, `-c` | Copia el Markdown del último commit sin crear ZIP. |
| `-g` | Incluye `git--diff_last_commit.md`. |
| `--no-env-example` | Excluye `.env.example`, `.env.sample` y `.env.template`. |

Las exclusiones de CLI no aceptan rutas absolutas, `~`, `..`, archivos ni rutas fuera del proyecto. Se normalizan una vez en la capa de aplicación y se aplican tanto al ZIP como al contexto Git.

## API para futuras interfaces

Una GUI debe depender de `PackService`, no del CLI ni de `pack_ai.py`:

```python
from pathlib import Path

from packai import PackRequest, PackService, ProgressEvent


def on_progress(event: ProgressEvent) -> None:
    # Adaptar a una barra, árbol, log o bus de eventos de la interfaz.
    print(event.kind, event.relative_path)


result = PackService().pack(
    PackRequest(
        root=Path("mi-proyecto"),
        output_zip=Path("mi-proyecto.zip"),
        exclude_paths=("cache",),
        include_git_context=True,
    ),
    reporter=on_progress,
)

print(result.output_zip, result.included_count, result.findings)
```

Contratos públicos:

- `PackRequest`: entrada validada del caso de uso.
- `PackResult`: salida inmutable con conteos, archivos incluidos y hallazgos.
- `ProgressEvent`: evento neutral para CLI, GUI o telemetría.
- `GitContextProvider`: puerto sustituible para Git real o dobles de prueba.
- `PackValidationError` y `ArchiveCreationError`: fallos esperados traducibles por cada interfaz.

## Política de seguridad

- `.env`, `.env.*` y variantes reales se excluyen incluso con `--force`.
- Los archivos de ejemplo de entorno se admiten solo si están habilitados y no contienen secretos detectados.
- Los hallazgos se enmascaran antes de formar parte de resultados o reportes.
- Los enlaces simbólicos no se siguen ni se agregan al ZIP.
- El ZIP se construye en un archivo temporal y reemplaza la salida de forma atómica únicamente cuando termina correctamente. Un fallo no destruye un ZIP anterior válido.
- La detección por expresiones regulares reduce riesgo, pero no garantiza ausencia de secretos. El ZIP debe revisarse antes de compartirlo.

## Configuración

- `.ignore2packai`: patrones `fnmatch`, uno por línea; se omiten líneas vacías y comentarios con `#`.
- `config_pack_ai.py`: conserva la opción `INCLUDE_ENV_EXAMPLE` por compatibilidad.
- `.python-version`, `pyproject.toml` y el `uv.lock` mantenido por el repositorio consumidor definen el entorno reproducible. El ZIP de esta entrega no sustituye ese lockfile.

## Calidad

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy src/packai
uv run pytest
uv run pytest --cov=packai --cov-fail-under=70
```

La estrategia y las decisiones durables están en:

- `docs/architecture.md`
- `docs/testing-strategy.md`
- `docs/adr/0001-stable-application-contracts.md`
- `CONTEXT.md`
- `AI_SKILLS.md`
