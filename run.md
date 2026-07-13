# Comandos recomendados

> Este ZIP no incluye ni modifica `uv.lock`. Integra los archivos y actualiza tu lockfile propio.

## Resolver dependencias

```bash
pyenv install -s 3.12.10
pyenv local 3.12.10
uv lock
uv sync --locked --extra gui
```

Solo CLI, sin dependencias gráficas:

```bash
uv sync --locked
```

## Gate completo

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy src/packai
uv run pytest
uv run pytest --cov=packai --cov-fail-under=70
```

## Pruebas dirigidas

```bash
uv run pytest tests/unit/test_gui_api.py
uv run pytest tests/unit/test_gui_cli.py
uv run pytest tests/unit/test_gui_commands.py
uv run pytest tests/unit/test_gui_launcher.py
uv run pytest tests/unit/test_gui_tree.py
uv run pytest tests/unit/test_gui_watcher.py
uv run pytest tests/unit/test_tokenization.py
uv run pytest tests/contract
uv run pytest tests/test_pack_ai.py
```

## Verificar tokenizador offline

```bash
uv run python -c "from packai.tokenization import build_default_token_estimator; r=build_default_token_estimator().estimate('hola mundo'); print(r)"
```

El resultado normal debe indicar `tiktoken:o200k_base` y `degraded=False`. El conteo preciso debe funcionar sin acceso a internet. Si aparece `heuristic:utf8-bytes/4`, el ZIP seguirá funcionando, pero el entorno no pudo cargar o verificar el tokenizador exacto.

## Smoke test del CLI

```bash
uv run packai --version
uv run packai . --copy none --token-top 10 --output ../pack-ai-smoke.zip
```

## Smoke test de la GUI

```bash
uv run packai gui --help
uv run packai gui .
```

Prueba manual mínima:

1. Comprueba que cada carpeta habilitada muestre su tamaño recursivo en B, KB, MB o GB.
2. Verifica que `node_modules` aparezca bloqueado, sin tamaño, y que su contenido no afecte al tamaño del padre.
3. Desmarca una carpeta y comprueba el estado indeterminado de su ancestro.
4. Verifica que las métricas se recalculen.
5. Activa y desactiva `Force` y contexto Git.
6. Crea o modifica un archivo y comprueba la actualización por eventos o sondeo.
7. Pulsa `Generar ZIP` dos veces después de modificar el proyecto.
8. Copia ambos comandos reproducibles y comprueba su sintaxis.

En Windows, si la ventana no inicia aun con el extra instalado:

```powershell
winget install -e --id Microsoft.EdgeWebView2Runtime
```

Si `winget` falla, instala o repara Microsoft Edge WebView2 Evergreen Runtime desde Microsoft. En Linux, el extra `gui` instala Qt; ejecuta la prueba dentro de una sesión gráfica X11 o Wayland.

## Instalación Windows del proyecto

```powershell
.\install.ps1
packai gui .
```

Para instalar únicamente el CLI:

```powershell
.\install.ps1 -NoGui
```
