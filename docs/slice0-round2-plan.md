# Slice 0 — cierre adicional autorizado, 2026-10-13

El padre pidió una revisión independiente del diff y completar las verificaciones
implementables en el mismo entorno. No autoriza commit, push, despliegue, credenciales
ni acceso persistente real. Se preserva la entrega original en
`/workspace/legalize-slice0-review/round1-original`.

## Revisión e instrucciones

Se asignó el diff completo al revisor separado `/root/independent_review`. Sus
pruebas iniciales reproducen una aprobación con legislación DOF construida con
datos declarados por cliente y divergencias entre recibo/ejecución que no bloquean
el outbox. Se corregirán y se solicitará una nueva revisión del resultado final.

No existe AGENTS.md ni .agents/skills en el commit base ni una instrucción heredada
aplicable en /workspace. Se releen .claude/CLAUDE.md y context/root-AGENTS.md; esta
última es copia histórica con alcance original /root. No requieren aprobación
específica para preparar historias/dependencias. El alcance explícito del usuario
autoriza el diff local. Se mantendrán las políticas JSON canónicas sin cambios.

## Implementación prevista

1. Verificar calendario en un archivo completo de main con misma venv. Guardar log
   separado; no atribuir al candidato el fallo demostrado en ese baseline.
2. Validar todos los campos execution/evidence/receipt/outbox entre sí, incluidos
   actor, expediente, versión, hashes, verdict y execution ID. Nunca aceptar como
   prueba una estructura de evidencia enviada por cliente.
3. Cerrar adapters de autoridad que solo confirman disponibilidad o devuelven texto
   de citation.quote. La legislación requiere quote/locator/title contrastados con
   texto obtenido por servidor, no con metadata autodeclarada.
4. Extraer TXT/PDF/DOCX desde bytes persistidos, ignorando extracted_text del cliente.
   Proponer pypdf 6.20.1 y python-docx 1.2.0, revisadas contra documentación oficial.
   Procesar formatos en un worker local con límites de bytes, páginas, memoria y
   tiempo; rechazar cifrado, archivos malformados, imágenes sin texto y funciones
   no soportadas. Vincular hash original, texto extraído y método al execution ID.
5. Convertir la CLI histórica de liberación en cliente del API autenticado, sin
   argumento de actor/verdict/fixture/política. El evaluator de gates queda separado
   del entry point y no emite APPROVED ni artefactos de liberación por sí mismo.
   Cerrar --skip-release para que solo produzca candidato pendiente de liberación.
6. Integrar interfaz de revisión con bearer del usuario aportado por la sesión,
   transmitido directamente al servidor MCP protegido; sin API key compartida en
   liberación, identidad en payload, autoalta o almacenamiento persistente del token.
   El bundle debe ser completo; la interfaz muestra gates y solo consume la ejecución
   que devuelve el servidor para ese mismo bundle/version.
7. Probar contrato con JWKS sintético y HTTP real de loopback. Las claves de firma
   son fixtures efímeras de test, no credenciales de un proveedor/producto real.
8. Usar PostgreSQL oficial en un contenedor temporal, red privada temporal y puerto
   solo loopback; sin passwords ni servicios productivos. Probar migración completa,
   concurrencia y outbox. Eliminar exclusivamente esos recursos temporales al terminar.
9. Revalidar diff completo y empaquetar patch, archivos cambiados, manifiestos y logs
   en una entrega accesible desde Library al padre. Conservar la entrega original.

La aceptación del candidato por pruebas sintéticas/locales se reportará separada de
la aceptación de despliegue. La recuperación histórica sigue siendo un límite de
integración. Slice 0 no se declara completo mientras falte una frontera requerida.

## Correcciones de segunda revisión

Restaurar enums SQLite para que main pueda leer después del downgrade; construir
source_url jurisprudencial exclusivamente desde el endpoint consultado por servidor;
rechazar texto PDF invisible, estados gráficos/operadores no soportados y estilos
DOCX ocultos. Se añade defusedxml 0.7.1 para analizar todos los XML del DOCX con DTD,
entidades y referencias externas prohibidos, según documentación oficial; ningún
archivo local exige checkpoint de aprobación de esta dependencia. Confirmación UI
comprobará una generación del contexto después de await para no mostrar el recibo
de una sesión/selección anterior como resultado actual. Probar cada reproducción.
