# 📦 Pack AI

**Pack AI** es una herramienta de línea de comandos diseñada para empaquetar proyectos en un archivo ZIP optimizado para su revisión por Inteligencia Artificial (ChatGPT, Gemini, Claude, etc.), asegurando la exclusión de archivos pesados y reduciendo el riesgo de filtrar secretos.

## ✨ Características principales

- **🚀 Comando Global**: Instalación sencilla para usar `packai` desde cualquier carpeta.
- **🛡️ Auditoría de Secretos**: Escaneo proactivo de claves API, tokens y credenciales con reportes detallados (tipo y número de línea).
- **🌳 Visualización Estructurada**: Muestra un árbol real del contenido que se está empaquetando.
- **📋 Copiado Automático**: Copia el archivo ZIP resultante directamente al portapapeles (en Windows).
- **⚙️ Configuración Flexible**: Soporte para archivos `.aiignore` (exclusión total) y `.aipass` (inclusión sin escaneo).
- **📄 Manejo Inteligente de Entornos**: Permite incluir archivos `.env.example` de forma segura (siempre que no contengan secretos reales).

## 🚀 Instalación en Windows

Para instalar `packai` como un comando global en tu sistema:

1. Clona este repositorio.
2. Abre una terminal en la carpeta del proyecto.
3. Ejecuta el instalador automático:
   ```powershell
   powershell -ExecutionPolicy Bypass -File .\install.ps1
   ```
4. **Reinicia tu terminal**. ¡Listo! Ahora puedes usar `packai` en cualquier sitio.

### Desinstalación
Si deseas eliminar el rastro de la herramienta y el comando global:
```powershell
powershell -ExecutionPolicy Bypass -File .\uninstall.ps1
```

## 🛠️ Uso

```bash
# Empaquetar la carpeta actual
packai

# Empaquetar una ruta específica
packai C:\Ruta\De\Mi\Proyecto

# Opciones avanzadas (deben ir antes de la ruta)
packai --copy path --output mi_respaldo.zip .
```

### Opciones disponibles

| Opción | Valores | Descripción |
|---|---|---|
| `--copy` | `file`, `path`, `none` | Qué se copia al portapapeles (por defecto: `file`). |
| `--output` | `[ruta]` | Ruta del ZIP generado (por defecto: `../nombre.zip`). |
| `--no-env-example` | (flag) | Si se activa, excluye archivos `.env.example` y similares. |

## ⚙️ Configuración Personalizada

- **`.aiignore`**: Funciona como un `.gitignore`. Lo que pongas aquí no entrará en el ZIP.
- **`.aipass`**: Archivos que quieres incluir en el ZIP pero que **no quieres que sean escaneados** (útil para archivos con claves falsas de test que el escáner bloquea por error).
- **`config_pack_ai.py`**: Archivo central para cambiar comportamientos por defecto del script.

## 🛡️ Seguridad y Limitaciones

**Pack AI** reduce el riesgo, pero **no garantiza una detección del 100%**. 

- El escaneo se basa en patrones Regex. No detecta secretos en formatos desconocidos.
- Siempre revisa el reporte de "Excluidos" al finalizar el empaquetado.
- Los archivos binarios y carpetas comunes (`node_modules`, `.git`, etc.) se ignoran por defecto para mantener el ZIP ligero.

---
Desarrollado para optimizar el flujo de trabajo con IAs de código.
