# Glosario

| Término | Significado en EduMaster.ai |
|---|---|
| Institución (tenant) | Organización cliente. Sus datos están aislados de las demás. |
| Rol | Conjunto de permisos (RBAC). Un usuario puede tener varios. |
| Permiso | Acción concreta, por ejemplo `user.manage`. El backend lo verifica en cada petición. |
| ABAC | Reglas por atributo: institución, curso asignado o propiedad del registro. |
| Token de acceso | Credencial JWT de 15 minutos que acompaña cada petición a la API. |
| Token de renovación | Credencial guardada en una cookie protegida que obtiene un nuevo token de acceso; se reemplaza en cada uso. |
| Bitácora de auditoría | Registro inalterable de acciones críticas: quién, qué, cuándo y desde dónde. |
| `correlation_id` | Identificador que une una petición con sus logs, errores y eventos. |
| Cohorte | Grupo de estudiantes que cursa una oferta en el mismo periodo. |
| Oferta de curso | Edición concreta de un curso: periodo, docente y cohorte. |
| Ruta de aprendizaje | Secuencia de cursos con objetivos, competencias y prerrequisitos. |
| Evento de aprendizaje | Hecho registrado (lección vista, evaluación enviada), con `event_id` único. |
| Competencia | Habilidad del catálogo jerárquico, medida en 5 niveles de dominio. |
| DEMO | Dato sintético para probar el sistema; nunca se presenta como real. |
| Baseline | Modelo simple de referencia que la red neuronal debe superar. |
| Riesgo de abandono | Probabilidad estimada de desconexión; es apoyo al docente, nunca una sanción. |
| Model card | Ficha del modelo: datos, métricas, límites y aprobación. |
| Fuga de información | Usar en el entrenamiento datos que no existirían al momento de predecir. |
| Outbox | Tabla donde se guardan eventos en la misma transacción para publicarlos sin pérdidas. |
| Cloudflare Tunnel | Conexión saliente que publica el sistema local con HTTPS sin abrir puertos. |
