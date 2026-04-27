# 📦 Pack AI

**Pack AI** es una herramienta de línea de comandos (CLI) diseñada para empaquetar proyectos en archivos ZIP optimizados para el análisis con modelos de IA (como ChatGPT, Claude o Gemini).

## ✨ Características Principales

- 🛡️ **Escaneo de Secretos Proactivo**: Detecta tokens de API (OpenAI, Groq, Anthropic, AWS, etc.) y asignaciones de variables sensibles en dos capas (Alta Confianza y Contextual).
- 🚀 **Recorrido de Directorios Optimizado**: Ignora carpetas pesadas como `node_modules`, `.venv` o `.git` de forma recursiva sin siquiera entrar en ellas, garantizando una velocidad máxima.
- 📋 **Integración con Portapapeles**: Copia automáticamente el archivo ZIP resultante (o su ruta) al portapapeles de Windows para que solo tengas que hacer `Ctrl+V` en tu chat de IA.
- 🔒 **Seguridad Reforzada**: Salta automáticamente archivos de más de 1MB y enlaces simbólicos (`symlinks`) para evitar fugas de datos accidentales.

## ⚙️ Configuración de Exclusiones

Puedes controlar qué archivos entran en el ZIP y cuáles se analizan mediante dos archivos opcionales:

### 1. `.aiignore` (Exclusión Total)
Los archivos o carpetas que coincidan con los patrones de este archivo **no se incluirán en el ZIP**. Es ideal para dependencias, archivos binarios pesados o carpetas de build.

### 2. `.aipass` (Bypass del Analizador)
Los archivos que coincidan con los patrones de este archivo **se incluirán en el ZIP sin ser analizados por el escáner de secretos**.
Es útil para archivos que contienen patrones que disparan falsos positivos pero que necesitas compartir con la IA (como este propio script).

> [!CAUTION]
> **ADVERTENCIA DE SEGURIDAD**: Los archivos listados en `.aipass` se añadirán "sí o sí" al ZIP sin ninguna verificación. Es extremadamente peligroso añadir aquí archivos que contengan llaves privadas reales, ya que el analizador no te avisará y podrías filtrarlas accidentalmente a la IA.

## 🚀 Instalación

Esta herramienta utiliza [uv](https://github.com/astral-sh/uv) para una gestión de dependencias ultrarrápida.

```bash
git clone <url-del-repo>
cd pack_ai
uv sync
```

## 🛠️ Uso

```bash
uv run python pack_ai.py <ruta_del_proyecto>
```

### Opciones de Copiado

- `--copy file` (Por defecto): Copia el archivo ZIP.
- `--copy path`: Copia la ruta absoluta.
- `--copy none`: No copia nada.

## 🛡️ Seguridad

Pack AI es **auditable y seguro**. No requiere dependencias externas y utiliza comandos nativos de Windows (PowerShell). El escaneo de secretos nunca envía datos fuera de tu máquina local.
