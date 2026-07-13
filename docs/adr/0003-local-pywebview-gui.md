# ADR 0003: GUI local PyWebView con selección jerárquica de carpetas

## Estado

Aceptado

## Contexto

El empaquetado necesitaba una superficie visual para excluir subárboles, consultar métricas y repetir iteraciones sin reconstruir manualmente comandos. El CLI existente debe conservar su comportamiento y el núcleo no debe depender de una tecnología de interfaz.

La GUI debe funcionar sin servidor web, recursos remotos ni estado persistente. También debe reaccionar a cambios del proyecto sin comprimir en cada interacción y debe fallar de forma aislada cuando el equipo no tenga un backend gráfico.

## Decisión

1. Añadir `packai gui [folder]` como subcomando detectado antes del parser heredado.
2. Mantener PyWebView y watchdog en el extra opcional `gui`.
3. Cargar React 18 y los recursos HTML/CSS/JavaScript desde el paquete instalado, sin CDN.
4. Exponer a JavaScript un puente Python pequeño que solo traduce datos serializables y delega en `PackService.preview` y `PackService.pack`.
5. Representar únicamente carpetas como nodos seleccionables. Las exclusiones se expresan como el conjunto mínimo de rutas relativas compatible con el CLI.
6. Mostrar carpetas bloqueadas por política como hojas deshabilitadas y no recorrer sus subárboles.
7. Mantener la selección solo en memoria durante la sesión.
8. Usar eventos de watchdog con debounce; si no están disponibles, usar sondeo de baja frecuencia. Cada generación reescanea el proyecto aunque la vista previa parezca actual.
9. No permitir elegir una salida desde la GUI. Se conserva el nombre predeterminado derivado del proyecto y Git.
10. Devolver errores accionables y mantener disponible el CLI si PyWebView, WebView2 o el backend gráfico fallan.

## Consecuencias

### Positivas

- El CLI y la GUI comparten reglas, métricas, seguridad y escritura atómica.
- Una selección puede reproducirse copiando un comando CLI.
- El CLI no instala dependencias gráficas cuando no se solicitan.
- No existe proceso de Node, servidor local ni acceso de red durante la ejecución.
- Las iteraciones repetidas reflejan el sistema de archivos actual.

### Negativas

- Los recursos React se versionan dentro del paquete y requieren actualización deliberada.
- Los backends gráficos dependen del sistema operativo.
- Reincorporar un descendiente de una carpeta excluida puede generar varias exclusiones hermanas porque el contrato público solo expresa carpetas excluidas.
- El monitor de eventos es una optimización; la corrección depende del reescaneo previo a `pack`.

## Alternativas consideradas

- **Aplicación web con servidor local:** rechazada por añadir puertos, ciclo de vida y superficie de seguridad innecesarios.
- **Frontend con compilación Node/Vite:** rechazado para evitar otro toolchain en un proyecto Python pequeño.
- **Watcher obligatorio:** rechazado porque un backend puede no estar disponible; el fallback mantiene funcionalidad.
- **Persistir `.packai-gui.json`:** rechazado en esta versión para no modificar el proyecto ni crear migraciones de configuración.
