# Comandos recomendados

> Este ZIP no incluye ni modifica `uv.lock`. `pyproject.toml` añade `tiktoken`; actualiza tu propio lockfile después de integrar los cambios.

## Resolver la nueva dependencia en tu lockfile

```bash
pyenv install -s 3.12.10
pyenv local 3.12.10
uv lock
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
uv run pytest tests/unit/test_metrics.py
uv run pytest tests/unit
uv run pytest tests/contract
uv run pytest tests/test_pack_ai.py
```

## Verificar tokenizador principal

```bash
uv run python -c "from packai.tokenization import build_default_token_estimator; e=build_default_token_estimator(); r=e.estimate('hola mundo'); print(r)"
```

El resultado normal debe indicar `tiktoken:o200k_base` y `degraded=False`. Si aparece `heuristic:utf8-bytes/4`, el ZIP seguirá funcionando, pero el entorno no pudo cargar `tiktoken`.

## Smoke test de métricas y CLI

```bash
uv run packai --version
uv run packai . --copy none --token-top 10 --output ../pack-ai-smoke.zip
```

## Preview para una futura GUI

```bash
uv run python -c "from pathlib import Path; from packai import PackRequest, PackService; p=PackService().preview(PackRequest(root=Path('.'), output_zip=Path('../preview.zip'))); print(p.metrics); assert not Path('../preview.zip').exists()"
```
