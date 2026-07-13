# Comandos recomendados

> Este ZIP no incluye ni modifica `uv.lock`. Los comandos siguientes usan el `uv.lock` existente en tu repositorio.

## Preparar el entorno

```bash
pyenv install -s 3.12.10
pyenv local 3.12.10
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
uv run pytest tests/unit
uv run pytest tests/contract
uv run pytest tests/test_pack_ai.py
```

## Smoke test del paquete y CLI

```bash
uv run python -c "from packai import PackService, PackRequest; print(PackService, PackRequest)"
uv run packai --version
uv run packai . --copy none --output ../pack-ai-smoke.zip
```

En Windows, el último comando también puede ejecutarse después de `install.ps1` como `packai . --copy none --output ..\pack-ai-smoke.zip`.
