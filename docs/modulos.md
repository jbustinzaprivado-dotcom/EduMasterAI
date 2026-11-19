# Módulos de EduMaster.ai: cómo funciona cada uno y por qué se construyó así

Guía para entender y defender el sistema en la exposición. Cada módulo responde a:
- **Para qué sirve** y **quién lo usa**.
- **Cómo funciona**, paso a paso.
- **Dónde está el código**.
- **Por qué así:** la decisión tomada frente a las alternativas, con su número Dxx de
  [`fase-0/decisiones.md`](fase-0/decisiones.md) y la sección del Documento Maestro (§).
- **Cómo mostrarlo:** qué hacer en la demo para que se vea.

Para una explicación sin tecnicismos ver [`como-funciona.md`](como-funciona.md). Para operar el sistema, ver
[`runbooks.md`](runbooks.md).

---

## 0. Arquitectura general

**Cómo funciona.** El navegador carga una aplicación React (la web). Esa aplicación habla con una API FastAPI
(Python) mediante JSON. La API guarda todo en una base de datos relacional: SQLite en la demo y PostgreSQL en la CI.
La misma API entrega la web compilada, así que toda la plataforma tiene **una sola dirección pública**, que el
túnel de Cloudflare expone a Internet.

```
Navegador ──HTTPS──▶ Cloudflare Tunnel ──▶ API FastAPI (puerto 8000) ──▶ Base de datos
                                              │  └─ sirve la web compilada (React)
                                              └─ modelo de IA (pesos NumPy) en el mismo proceso
```

**Código.**
- `apps/api/app/modules/<dominio>`: un paquete por área de negocio.
- `apps/web/src/modules/<módulo>`: una carpeta por pantalla.
- `ml/`: dataset y entrenamiento del modelo.

**Por qué así.**

| Decisión | Alternativas | Por qué |
|---|---|---|
| **Monolito modular** (un proceso con módulos separados, §6.1) | Microservicios | Un equipo pequeño y un solo PC. Los módulos ya están separados por dominio, así que separarlos en servicios más adelante no exige rehacerlos. |
| **Una sola puerta pública:** la API sirve la web (D03) | Web y API en dominios distintos | Evita CORS, cookies entre dominios y dos túneles. Además, la cookie de sesión puede ser `SameSite=Strict`. |
| **PC propio + Cloudflare Tunnel** (D03) | Hosting en la nube (Render, Railway, VPS) | Sin costo y sin límites de RAM para el modelo. HTTPS y protección ante ataques los pone Cloudflare. El PC no abre puertos en el router. |
| **FastAPI + SQLAlchemy + Alembic** (§6.1) | Django, Node/Express | Es lo que recomienda el documento. Python es el mismo lenguaje del modelo, valida con tipos (Pydantic) y genera OpenAPI automáticamente. |
| **React 19 + TypeScript + Vite + Tailwind** (D12) | Angular, Vue | Lo recomienda el §6.1. El tipado estricto evita errores entre la web y la API. |
| **SQLite en la demo y PostgreSQL en la CI** (D13) | Solo PostgreSQL | La demo se instala con doble clic, sin servidor de base de datos. La CI repite todas las pruebas sobre PostgreSQL, así que el código sirve para ambos. |

---

## 1. Autenticación y sesiones

**Para qué.** Saber quién es cada persona y mantener su sesión de forma segura. Lo usan todos.

**Cómo funciona.**
1. La persona escribe el código de institución, su correo y su contraseña. El correo es único dentro de cada institución (D09).
2. La API compara la contraseña con su hash PBKDF2-SHA256 de 600 000 iteraciones. Si algo falla, responde siempre el mismo mensaje genérico, para no revelar qué dato estaba mal.
3. Si es correcta, entrega dos llaves:
   - un **token de acceso** JWT que dura 15 minutos y la web envía en cada petición;
   - un **token de renovación** guardado en una cookie `httpOnly`, `Secure` y `SameSite=Strict`, que JavaScript no puede leer.
4. Cuando el token de acceso vence, la web pide uno nuevo con la cookie. El token de renovación **rota** en cada uso. Si alguien reutiliza uno viejo, señal de robo, se cierra toda la sesión.
5. Hay un límite de intentos: 10 por minuto por IP y correo, y 60 por minuto por IP (D46).

**Código.** `identity/router_auth.py`, `identity/service.py`, `core/security.py`, `core/rate_limit.py`. En la web: `lib/auth.tsx` y `modules/auth`.

**Por qué así.**

| Decisión | Alternativas | Por qué |
|---|---|---|
| **OAuth2 propio de la API** (D08) | Keycloak u otro proveedor OIDC | Keycloak es otro servidor que habría que instalar y exponer con un segundo túnel. El diseño es compatible con OIDC: más adelante se puede conectar el login institucional. |
| **Token corto + renovación en cookie** | Un solo token largo en `localStorage` | Un token en `localStorage` lo roba cualquier XSS. Aquí el de acceso vive en memoria 15 minutos y el de renovación no es accesible desde JavaScript. |
| **Límite por IP y correo** (D46) | Límite solo por IP | La simulación de un día de clases mostró que el límite por IP bloqueaba a la persona 11 de un aula con el mismo Wi-Fi. |
| **Código de institución en el login** (D09) | Solo correo | Así una misma persona puede tener cuentas en dos instituciones y nunca se mezclan. |

**Cómo mostrarlo.** Entrar con una contraseña errónea: el mensaje no dice qué falló. Recargar la página: la sesión sigue abierta.

---

## 2. Roles, permisos e instituciones (multi-tenant)

**Para qué.** Que cada persona vea y haga solo lo que le corresponde, y que una institución nunca vea a otra.

**Cómo funciona.**
- **Roles y permisos (RBAC).** Hay 8 roles (§3). Cada uno es una lista de permisos, como `course.manage`, `ml.approve` o `ops.read`. El catálogo vive en el código (`catalog.py`) y se sincroniza con la base al arrancar. Cada endpoint declara el permiso que exige con `require("permiso")`.
- **Por atributos (ABAC).** Además del rol se mira la relación con el dato: un docente solo ve sus ofertas y un estudiante solo sus matrículas. Todo pasa por `offerings_query`.
- **Separación de instituciones.** Cada tabla tiene `organization_id` y cada consulta filtra por la institución de quien pregunta. Un recurso de otra institución responde **404**, no 403, para no revelar que existe.
- **En la web.** Ocultar un botón es solo comodidad visual. La seguridad real está en la API.

**Código.** `identity/catalog.py`, `api/deps.py` (`require` y `get_principal`), `academic/service.py` (`offerings_query`), `tests/test_permisos_y_aislamiento.py`.

**Por qué así.**

| Decisión | Alternativas | Por qué |
|---|---|---|
| **Columna `organization_id` en tablas compartidas** (D04) | Un esquema o una base de datos por institución | Con muchas instituciones, una base por institución multiplica las migraciones y los respaldos. La columna es lo más simple y se prueba con tests de aislamiento. |
| **Aislamiento en la aplicación, sin RLS por ahora** (D45) | Row Level Security de PostgreSQL | El §11 la plantea como frontera *adicional* opcional. La demo usa SQLite, que no tiene RLS. Queda como siguiente paso cuando haya datos reales. |
| **404 para otra institución** | 403 | Un 403 confirma que el recurso existe; un 404 no revela nada. |
| **Catálogo de permisos en el código** | Permisos editables desde la web | Los permisos cambian junto con el código que los usa. Así quedan versionados y probados. |

**Cómo mostrarlo.** Entrar como `admin@pacifico.demo` y abrir la URL de una oferta de ANDINO: responde 404. Entrar como estudiante: el menú no muestra Analítica, y si se fuerza la URL la API responde 403.

---

## 3. Bitácora de auditoría

**Para qué.** Registrar quién hizo qué y cuándo en toda acción crítica (§11.1). La revisan la auditoría y la administración, y cada persona puede ver su propia actividad.

**Cómo funciona.**
- Cada acción importante (login, cambio de rol, nota, certificado, aprobación de modelo, exportación) llama a `record()` en la **misma transacción**. Si la acción falla, tampoco queda registro.
- Cada registro guarda el actor, la institución, el recurso, los detalles, la IP real (cabecera `CF-Connecting-IP` del túnel) y el `correlation_id`.
- En PostgreSQL un *trigger* impide hacer UPDATE o DELETE: la bitácora solo crece.
- Se pagina por cursor, no por número de página, para que sea estable aunque lleguen registros nuevos.

**Código.** `audit/`, migración `0001_identidad_y_auditoria.py` (el trigger). En la web: `modules/audit`.

**Por qué así.** Se descartó registrar con un *listener* genérico de SQLAlchemy porque registra cambios técnicos, no acciones con significado ("aprobó el modelo X con esta nota"). El trigger hace que ni un error en la aplicación pueda alterar el historial.

**Cómo mostrarlo.** Aprobar el modelo y abrir **Actividad y auditoría**: aparece `model.published` con el actor y la hora.

---

## 4. Cursos, ofertas, matrículas y lecciones

**Para qué.**
- La administración crea cursos y abre ofertas: periodo, docente y cohorte.
- Los estudiantes avanzan por las lecciones.
- El docente edita el contenido.

**Cómo funciona.**
- **Estructura.** Un **curso** tiene unidades y actividades (lectura, video, práctica). Una **oferta** es una edición concreta del curso: periodo, docente y cohorte. Una **matrícula** une a un estudiante con una oferta.
- **Lecciones.** Son texto con formato ligero (títulos, listas, negrita, código), recursos y un enlace a video. Cada edición sube la versión y queda en la auditoría (D36).
- **Progreso.** Se recalcula con cada evento de aprendizaje (módulo 5): es el porcentaje de actividades obligatorias completadas.

**Código.** `academic/router.py`, `academic/lessons.py`, `academic/service.py`. En la web: `modules/courses` (`OfferingPage` y `LessonPage`).

**Por qué así.**

| Decisión | Alternativas | Por qué |
|---|---|---|
| **La cohorte es un campo de la oferta** (D15) | Una entidad "grupo" aparte | Basta para asignar y filtrar. Si un grupo cursa varias ofertas juntas, se separa después. |
| **Texto con formato propio, nunca HTML** (D36) | Editor HTML enriquecido | Interpretar HTML del docente abre la puerta a XSS. Una prueba lo verifica. |
| **Video por enlace** | Subida de archivos | Subir archivos exige almacenamiento, antivirus y URLs firmadas (§11). Se pospuso hasta tenerlos. |

**Cómo mostrarlo.** Como docente, editar una lección: la versión sube. Como estudiante, marcar una actividad: la barra de progreso avanza.

---

## 5. Eventos de aprendizaje (tracking)

**Para qué.** Registrar lo que hace el estudiante (sesión, lección vista, actividad iniciada o completada, minutos). Es la materia prima de los indicadores, la IA y la analítica.

**Cómo funciona.**
- El navegador genera un `event_id` único para cada evento y lo envía con `POST /learning-events`.
- Si el mismo evento llega dos veces, por ejemplo porque se cortó la red y se reintentó, la API lo reconoce y responde `duplicate: true` sin contarlo de nuevo. Eso es la **idempotencia** (§10.2).
- La duración se limita a 0–4 horas, para rechazar datos absurdos.
- La API solo acepta eventos propios, de cursos donde la persona está matriculada.

**Código.** `academic/router.py` (`ingest`) y `academic/service.py` (`ingest_event`).

**Por qué así.** Se descartó el "contador simple" (sumar 1 por petición) porque con reintentos de red infla los datos, y con ellos los indicadores y el modelo. El identificador lo genera el cliente porque es el único que sabe si está reintentando.

**Cómo mostrarlo.** La simulación (`scripts/simulacion.py`) reenvía cada evento de sesión y comprueba que se marca como duplicado. En la prueba del 19-11 fueron 20 de 20.

---

## 6. Evaluaciones y notas

**Para qué.** El docente crea evaluaciones, el estudiante entrega y el docente pone la **nota oficial**.

**Cómo funciona.**
- Cada evaluación tiene un tipo, un peso, una fecha límite y un número máximo de intentos. Los pesos de una oferta suman como máximo 100 %.
- La entrega fuera de plazo queda marcada como tardía.
- La nota usa la escala 0–20. Cuenta el mejor intento calificado y el promedio se pondera por peso (D18).
- Al calificar, el estudiante recibe el aviso **en vivo** (módulo 9).

**Código.** `academic/router.py` (assessments, submissions, attempts). En la web: `modules/courses` y la página Evaluaciones.

**Por qué así.**

| Decisión | Alternativas | Por qué |
|---|---|---|
| **Escala vigesimal (0–20)** (D18) | 0–100 | Es la escala usual en Perú. El máximo es configurable por evaluación. |
| **Nota oficial separada de la IA** (§4.6) | Que la IA califique | Una nota decide cosas de la persona. La IA solo estima y apoya; la nota la pone una persona. |

---

## 7. Rutas de aprendizaje

**Para qué.** La coordinación arma una secuencia de cursos, por ejemplo "Analista de datos junior": PY-101 → DS-201 → ML-301, y la asigna a personas o cohortes.

**Cómo funciona.**
- Las etapas van en orden y cada una exige completar la anterior (prerrequisito secuencial). Una etapa puede exigir además una nota mínima.
- Editar una ruta publicada sube su versión.
- Las excepciones, como saltar un prerrequisito, necesitan un motivo y quedan auditadas.
- El estudiante ve su avance como una línea de tiempo, con las etapas bloqueadas hasta cumplir la anterior.

**Código.** `paths/` y en la web `modules/paths`.

**Por qué así (D32).** Se descartó un grafo libre de prerrequisitos (tipo "malla" con ramas) porque complica la interfaz y la explicación, y el documento solo pide secuencias. Las competencias se guardan como etiquetas hasta que existió el catálogo de habilidades.

---

## 8. Panel de resumen (dashboard)

**Para qué.** Una vista de cómo va la institución, los cursos del docente o el propio estudiante.

**Cómo funciona.**
- **Indicadores.** Cada KPI se calcula en el momento desde la base y muestra su **valor, la variación frente al periodo anterior, la fuente y la hora de cálculo** (§13.1, criterio 25).
- **Alcance según el rol.**

  | Rol | Qué ve |
  |---|---|
  | Administración | La institución |
  | Superadministración | Toda la plataforma |
  | Docente | Solo sus cursos (corregido el 19-11 en la simulación: los estudiantes y cursos también se cuentan solo de sus ofertas) |
  | Estudiante | Su resumen personal |

- **Contenido.** La composición sigue la imagen de referencia del manual (D39): la red neuronal con sus entradas y salidas, 4 indicadores principales, el progreso semanal, el mapa, la finalización, las habilidades, las recomendaciones, la actividad y la hoja de ruta.
- **Barra lateral.** Muestra la precisión real del modelo publicado y cuántas personas están conectadas.

**Código.** `dashboard/router.py`. En la web: `modules/dashboard/DashboardPage.tsx` y `components/layout/AppShell.tsx`.

**Por qué así.**

| Decisión | Alternativas | Por qué |
|---|---|---|
| **Datos reales, no los de la imagen** (D39) | Copiar las cifras de la referencia | El §1 prohíbe cifras inventadas. La imagen muestra "ingresos", pero aquí no hay facturación (§4.1), así que no se muestra. |
| **Gráficos SVG propios** (D17) | ECharts o Recharts | Pesan cientos de KB por el túnel. Los propios tienen leyenda, unidades, tooltip y estados vacío, carga y error. |
| **Calcular en cada consulta** | Tablas de agregados precalculados | Con este volumen responde en menos de 100 ms (prueba de carga). Los agregados se justifican con millones de eventos. |

---

## 9. Notificaciones en tiempo real

**Para qué.** Avisar al instante, sin recargar: nota publicada, evaluación nueva, certificado, alerta, respuesta en un debate o modelo publicado.

**Cómo funciona.**
1. La acción, por ejemplo calificar, crea la notificación en la **misma transacción** (patrón Outbox).
2. Solo si la transacción se confirma, se publica al canal en vivo del destinatario. Nunca se anuncia algo que luego se deshizo.
3. El navegador mantiene abierta una conexión **SSE** (Server-Sent Events). El servidor envía un latido cada 15 s para que el túnel no la corte.
4. Si se corta, el navegador reconecta con `Last-Event-ID` y recibe lo que se perdió.
5. Cada conexión es de **un solo usuario**. No hay canal global con datos de todos (§10.4).

**Código.** `notifications/service.py` (broker y `after_commit`) y `notifications/router.py` (`/stream`). En la web: la campana de `AppShell` y `lib/live.tsx`.

**Por qué así.**

| Decisión | Alternativas | Por qué |
|---|---|---|
| **SSE** (D28) | WebSocket | El flujo es solo servidor → navegador. SSE es HTTP normal, pasa por el túnel sin configurar nada y el navegador reconecta solo. |
| **Token en la cabecera**, leído con un *stream* de fetch | Token en la URL (`?token=`) | La URL queda en logs e historial. Con la cabecera no. |
| **Broker en memoria** (D11) | Redis Pub/Sub | Con una sola instancia basta. Con varias instancias se cambia el broker por Redis sin tocar los módulos. |
| **Guardar y luego publicar** | Publicar directamente | Si se publica y la transacción falla, el usuario ve un aviso falso. |

**Cómo mostrarlo.** Abrir dos navegadores: el docente califica y a la estudiante le aparece el aviso al instante. En la simulación del 19-11, Valeria recibió así la respuesta a su debate.

---

## 10. Certificados

**Para qué.** Emitir constancias oficiales verificables por cualquier persona.

**Cómo funciona.**
- Al completar el curso con nota final ≥ 11/20 y al menos 50 % del peso calificado, el certificado se emite **automáticamente** (D29). Lleva un folio único, un PDF con código QR y un código de verificación.
- Cualquier persona puede comprobarlo en `/verificar/<código>` sin cuenta. La página muestra solo los datos mínimos y tiene su propio límite de consultas.
- Para anularlo hace falta un motivo. Si se reemite, el certificado nuevo queda enlazado al anterior. Todo se audita.

**Código.** `certificates/`. En la web: `modules/certificates` y `VerifyPage`.

**Por qué así.** Se descartó la emisión manual, porque es lenta y propensa a errores, y también una firma con blockchain, porque es complejidad sin beneficio para el caso. El QR que apunta a la verificación pública es lo que usan las universidades. Un certificado nunca se borra: se anula con motivo, para mantener la trazabilidad.

**Cómo mostrarlo.** Descargar el PDF y abrir su enlace de verificación en una ventana privada. En la simulación se emitieron 6 certificados automáticamente cuando 6 estudiantes terminaron su curso.

---

## 11. Mapa de progreso y comunidad

**Mapa.**
- Muestra el progreso promedio por departamento del Perú, como un **cartograma de mosaicos**: un cuadrado por región.
- Las regiones con menos de 3 estudiantes no se muestran ni se nombran (**k-anonimato**, D30).
- Solo lo ven los docentes y la gestión.

| Alternativa | Por qué no |
|---|---|
| Mapa geográfico real (GeoJSON) | Pesa varios MB por el túnel. El mosaico se lee igual de bien. |
| Mapa mundial, como en la referencia | No aporta para una institución peruana. |

**Comunidad.**
- Cada oferta tiene su espacio de anuncios y debates.
- Participan los matriculados, su docente y la gestión; la auditoría solo lee (D31).
- Moderar es **ocultar con motivo** y queda auditado; nunca se borra.
- Cada persona puede silenciar un curso.

| Alternativa | Por qué no |
|---|---|
| Foro general de toda la institución | Mezcla cursos y expone a personas ante gente con la que no comparten clase. |

**Código.** `dashboard/router.py` (`/geo`), `community/`. En la web: `modules/community`.

---

## 12. Analítica y exportación

**Para qué.** Ver nueve indicadores: participación, tiempo activo, días activos, entregas, entregas a tiempo, intentos, progreso, finalización y nota. Se pueden filtrar y exportar.

**Cómo funciona.**
- Cada indicador muestra **su definición publicada** (al pasar el cursor).
- Filtros: fechas, oferta, cohorte, docente y periodo.
- El detalle por estudiante lo ven la gestión, el docente (de sus ofertas) y la auditoría. El analista solo ve agregados (D33).
- Se exporta a CSV (con `;` y BOM, para que Excel lo abra bien), XLSX y PDF, con la fecha y los filtros en el encabezado. **Cada exportación queda auditada.**

**Código.** `analytics/`. En la web: `modules/analytics`.

**Por qué así.** Se descartó un BI externo (Metabase, Power BI) porque exige otro servidor y duplicar los permisos. Aquí la analítica respeta las mismas reglas de acceso que el resto del sistema.

---

## 13. Dominio de habilidades

**Para qué.** Mostrar el nivel de cada competencia, de 0 a 4, en un mapa de calor.

**Cómo funciona.**
- Las competencias forman un catálogo de dos niveles (área → competencia). Cada curso enlaza sus competencias y cada evaluación declara cuáles evidencia.
- El nivel **estimado** lo calcula un motor de reglas a partir de las notas y el avance.
- El nivel **validado** lo fija el docente con una nota de evidencia, y es el oficial (D34).
- Los dos niveles se muestran **por separado**: la estimación nunca se confunde con el juicio del docente.

**Código.** `skills/`. En la web: `modules/skills`.

**Por qué así.** El documento prevé una cabeza de la red para esto (cabeza B de §9.1), pero no hay validaciones de docentes suficientes para entrenarla. Mientras tanto, un motor de reglas explicable es más honesto que un modelo entrenado con pocos datos.

---

## 14. Dataset DEMO y modelo neuronal de riesgo de abandono

**Para qué.** Estimar qué estudiantes podrían abandonar, para que el docente actúe a tiempo.

**Cómo funciona.**
1. **Dataset sintético** (D06, D16). `ml/src/edumaster_ml/generate.py` simula unas 13 400 matrículas con comportamientos latentes: constantes, irregulares y en riesgo, con desconexión progresiva y pausas. Usa una semilla fija y una huella SHA-256, y siempre va rotulado DEMO.
2. **Variables sin fuga.** Solo usa hechos anteriores a la fecha de corte. El mismo código calcula las variables al entrenar y al predecir.
3. **Separación temporal por cohorte.** Entrena con las cohortes antiguas, valida con las intermedias y prueba con las más recientes. Así se simula predecir el futuro, no repartir al azar.
4. **Modelos.** Se compararon dos baselines (regresión logística y Gradient Boosting) con una **red multitarea**:
   - una rama densa para las 8 variables;
   - una **GRU** para la secuencia semanal;
   - una capa de fusión;
   - y las cabezas de salida.
5. **Calibración Platt** (D25): un 70 % significa de verdad un 70 %. El umbral de alerta se elige en validación con recall ≥ 0,6.
6. **Regla de publicación** (D26): la red solo se elige si supera al baseline logístico en PR-AUC de validación sin empeorar el Brier. Ganó por poco: 0,625 contra 0,610 en prueba. Su ROC-AUC es del 86,6 %.
7. **Model card.** Recoge métricas por segmento, calibración, limitaciones y el historial de entrenamiento.

**Código.** `ml/src/edumaster_ml/` (`generate.py`, `train.py`), `ml/registry/` (pesos y model card), `ml/tests/`.

**Por qué así.**

| Decisión | Alternativas | Por qué |
|---|---|---|
| **Datos sintéticos rotulados** (D06) | Datos reales | No hay datos institucionales autorizados (Ley 29733). Lo sintético se reconstruye exacto y nunca se presenta como real. |
| **Comparar contra baselines con una regla fija** (D26) | Publicar la red porque "es más avanzada" | El §9.1 lo exige. Si la red no gana, se publica el baseline. La regla se fija **antes** de ver la prueba. |
| **GRU** | Transformer o LSTM | La secuencia es corta (semanas), así que una GRU basta con menos parámetros. Un Transformer sobreajustaría con estos datos. |
| **Partición temporal** | Partición aleatoria | La aleatoria mezcla futuro y pasado e infla las métricas. |
| **Pesos en Git (~90 KB) y dataset fuera** (D21) | DVC o MLflow | Para un solo modelo pequeño, DVC y MLflow agregan servidores sin beneficio. Quedan para cuando haya más modelos (D20). |

---

## 15. Publicación del modelo, alertas y vuelta atrás

**Para qué.** Que ningún modelo se use sin aprobación humana, y que sus alertas apoyen al docente sin etiquetar al estudiante.

**Cómo funciona.**
1. **Separación de funciones** (D23): el ML Engineer registra la versión y la administración de **cada institución** la revisa y la aprueba.
2. **Inferencia.** La API calcula con **NumPy** usando los pesos exportados (D24), sin PyTorch en el servidor. Una prueba verifica que NumPy da lo mismo que PyTorch.
3. **Alertas.** El docente ve el riesgo de sus estudiantes con los **factores que lo explican** y lo marca como atendido o descartado, siempre con una nota.
4. **El estudiante no ve su propio puntaje** (D22), para no etiquetarlo.
5. **Vuelta atrás** (D44): **Retirar** el modelo exige un motivo y queda auditado. Desde ese momento no salen alertas nuevas, el historial se conserva y la red vuelve al estado "Diseño".

**Código.** `ml/service.py`, `ml/router.py`. En la web: `modules/ml/ModelsPage.tsx` y la vista de riesgo de la oferta.

**Por qué así.**

| Decisión | Alternativas | Por qué |
|---|---|---|
| **Inferencia con NumPy** (D24) | Servir el modelo con PyTorch o TorchServe | PyTorch pesa unos 700 MB y otro servicio complica la demo. NumPy da el mismo resultado en milisegundos (0,25 s el p95 por oferta). |
| **Aprobación por institución** (D23) | Una aprobación global | Cada institución decide si confía en el modelo con su propia población. |
| **Revisión humana obligatoria** (§9.8) | Acciones automáticas, como avisar al estudiante | Una predicción equivocada que llega automáticamente al estudiante puede desmotivarlo. |

**Cómo mostrarlo.** Seguir los pasos 1–4 y 14 del guion del README.

---

## 16. Recomendaciones e IA Tutor

**Para qué.** Decirle al estudiante "¿qué hago ahora?", siempre con el motivo, y medir si la sugerencia le sirvió.

**Cómo funciona.**
- El motor `reglas-v1` (D27) genera cuatro tipos de sugerencia:
  - la siguiente actividad pendiente;
  - una entrega que vence pronto;
  - reforzar un tema tras una nota baja;
  - retomar el curso tras días de inactividad.
- El modelo de riesgo solo **sube la prioridad** de "retomar", sin mostrar el puntaje.
- Cada sugerencia pasa por los estados nueva, aceptada, descartada, completada y expirada. El estudiante puede marcarla como útil o no útil.
- Se mide la aceptación y la utilidad por tipo de sugerencia, no solo los clics.

**Código.** `recommendations/engine.py` y `router.py`. En la web: `modules/recommendations` (IA Tutor y Recomendaciones).

**Por qué así.**

| Decisión | Alternativas | Por qué |
|---|---|---|
| **Reglas explicables primero** (D27) | Un recomendador aprendido desde el inicio | Sin feedback real no hay con qué entrenarlo. Las reglas funcionan desde el primer día y **recogen el feedback** que entrenará la cabeza D (ranking aprendido) más adelante. |
| **Un LLM tipo chatbot** | — | Puede inventar contenido, cuesta por uso y su motivo no es verificable. Aquí cada sugerencia sale de un dato concreto del estudiante. |

---

## 17. Visualizador de la red neuronal

**Para qué.** Explicar el modelo de forma visual: sus capas, su estado y sus métricas.

**Cómo funciona.**
- La topología **viene de la API**, no está dibujada a mano.
- Sin un modelo publicado, la red aparece en estado "Diseño". La animación es una "SIMULACIÓN DEMO" que el usuario inicia y que lleva ese rótulo (D14).
- Respeta `prefers-reduced-motion`.
- Al hacer clic en una capa se ve su operación, sus unidades y su dimensión tensorial.

**Código.** `ml/router.py` (`/architecture`) y `modules/neural-visualizer`.

**Por qué así.** Se descartó una animación permanente "en vivo" porque haría creer que el modelo está procesando datos cuando no lo hace (§5.4, §13.1, criterio 27).

---

## 18. Operación y seguridad

**Para qué.** Proteger la plataforma pública y saber si está sana.

**Cómo funciona.**
- **Cabeceras de seguridad** (D40): CSP que solo permite scripts propios, anti-clickjacking, HSTS cuando hay HTTPS y `no-store` en la API.
- **Límites** (D40): 2 MB por petición y 600 peticiones por minuto por IP.
- **Pantalla Operación** (D41): latencia p50/p95/p99 por ruta, errores 5xx, conexiones en vivo, frescura de los datos y predicciones, comparadas con los objetivos del §10.5. Las rutas se registran por plantilla, sin identificadores, así que no hay datos personales.
- **Modelo de amenazas y revisión OWASP:** ver [`fase-7/seguridad.md`](fase-7/seguridad.md).

**Código.** `core/hardening.py`, `core/metrics.py`, `system/router.py` y `modules/operations`.

**Por qué así.** Se descartaron Prometheus y Grafana porque son dos servidores más para una sola instancia. Las métricas usan los nombres estándar, así que exportarlas después es directo.

---

## 19. Respaldo, carga y puesta en marcha

**Respaldo** (D42).
- `respaldo.bat` hace una copia en caliente cifrada con AES-256-GCM y la **prueba restaurándola** en una base temporal.
- Restaurar guarda antes la base actual, para poder deshacerlo.
- Objetivos: RPO de 24 h con una tarea diaria; RTO de minutos.

| Alternativa | Por qué no |
|---|---|
| Copiar el archivo de la base a mano | Si la API está escribiendo, la copia puede quedar corrupta. Además no se cifra ni se prueba. |

**Prueba de carga** (D43).
- `scripts/carga.py` simula usuarios por rol.
- Encontró un **bloqueo real**: el pool de 15 conexiones era menor que los 40 hilos de la API, y con carga todo se colgaba. Se corrigió.
- Resultados con 40 personas:

  | Operación | p95 | Objetivo | Cumple |
  |---|---|---|---|
  | Dashboard | 0,9 s | 2,5 s | ✅ |
  | Inferencia | 0,25 s | 0,8 s | ✅ |
  | Lectura común | 0,51 s | 0,5 s | En el límite |

**Simulación de un día real** (`scripts/simulacion.py`).
- Los 13 estudiantes avanzan, entregan y consultan al tutor; el docente califica y atiende alertas; se comprueban los controles de seguridad.
- Encontró dos problemas, ya corregidos:
  - el límite de inicio de sesión que bloqueaba a un aula (D46);
  - los indicadores del docente, que mostraban totales de la institución.

**Puesta en marcha** (D44).
- `demo.bat` ejecuta un **smoke test** antes de abrir el túnel. `comprobar.bat` lo repite cuando haga falta.
- Hay runbooks para cada situación: [`runbooks.md`](runbooks.md).

---

## 20. Pruebas automáticas

| Nivel | Qué cubre | Herramienta |
|---|---|---|
| API (89 pruebas) | Reglas de negocio, permisos, aislamiento, IA, seguridad, respaldo | pytest, sobre SQLite y PostgreSQL |
| ML | Sin fuga de datos, etiqueta correcta, NumPy = PyTorch | pytest |
| Web (7 pruebas) | Componentes y formato seguro del texto | Vitest |
| E2E (20 recorridos) | La web real en un navegador: login, permisos, accesibilidad (axe), móvil, notas en vivo entre dos navegadores, IA, certificados, analítica, operación y rollback | Playwright (D35) |

La CI de GitHub ejecuta los cuatro grupos en cada cambio.

| Alternativa | Por qué no |
|---|---|
| Cypress para E2E | Playwright maneja dos navegadores a la vez, que hace falta para la prueba de notas en vivo, y usa el Edge que ya está instalado en Windows. |
