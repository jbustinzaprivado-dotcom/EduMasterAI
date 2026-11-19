"""Contenido DEMO de las lecciones (§4.3). Idempotente: solo completa actividades sin contenido."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.academic.models import Course, CourseActivity, CourseUnit

PY_DOCS = "https://docs.python.org/es/3/tutorial/"
LESSONS = {
    "Instalación del entorno": (
        "## Objetivo\nTener Python listo para escribir y ejecutar tus primeros programas.\n\n"
        "## Pasos\n- Descarga Python 3 desde el sitio oficial e instálalo marcando «Add to PATH».\n"
        "- Abre una terminal y escribe `python --version` para comprobarlo.\n"
        "- Instala un editor como VS Code y su extensión de Python.\n\n"
        "## Para recordar\nSi `python` no se reconoce, cierra y vuelve a abrir la terminal.",
        [("Descargar Python", "https://www.python.org/downloads/"), ("Tutorial oficial en español", PY_DOCS)]),
    "Variables y tipos de datos": (
        "## Idea clave\nUna variable es un nombre que guarda un valor. Python deduce el tipo solo.\n\n"
        "## Ejemplos\n- `edad = 20` es un número entero (**int**).\n- `precio = 9.5` es decimal (**float**).\n"
        "- `nombre = \"Ana\"` es texto (**str**).\n- `activo = True` es lógico (**bool**).\n\n"
        "## Practica\nUsa `type(variable)` para ver el tipo de cada una.",
        [("Números, texto y listas", PY_DOCS + "introduction.html")]),
    "Práctica: calculadora": (
        "## Reto\nCrea una calculadora que pida dos números y una operación (+, -, *, /) y muestre el resultado.\n\n"
        "## Pistas\n- Usa `input()` y convierte con `float()`.\n- Controla la división entre cero.\n\n"
        "## Entrega\nMarca la actividad como completada cuando tu programa funcione con los cuatro casos.",
        []),
    "Condicionales": (
        "## Idea clave\n`if`, `elif` y `else` permiten elegir qué código se ejecuta.\n\n"
        "## Ejemplo\n- `if nota >= 11:` muestra «Aprobado».\n- `else:` muestra «Desaprobado».\n\n"
        "## Cuidado\nLa sangría (4 espacios) indica qué líneas pertenecen a cada bloque.",
        [("Herramientas de control de flujo", PY_DOCS + "controlflow.html")]),
    "Bucles for y while": (
        "## Idea clave\n`for` recorre una secuencia; `while` repite mientras una condición sea verdadera.\n\n"
        "## Ejemplos\n- `for i in range(5):` repite 5 veces.\n- `while intentos < 3:` repite hasta 3 intentos.\n\n"
        "## Practica\nCalcula el promedio de una lista de notas con un `for`.",
        [("Sentencias for y while", PY_DOCS + "controlflow.html#for-statements")]),
    "Práctica: adivina el número": (
        "## Reto\nEl programa elige un número del 1 al 100 y la persona tiene 7 intentos para adivinarlo.\n\n"
        "## Pistas\n- `import random` y `random.randint(1, 100)`.\n- Indica «más alto» o «más bajo» en cada intento.",
        []),
    "Funciones y parámetros": (
        "## Idea clave\nUna función agrupa código reutilizable: `def promedio(notas):` … `return total / len(notas)`.\n\n"
        "## Para recordar\n- Los parámetros son los datos de entrada.\n- `return` devuelve el resultado.",
        [("Definir funciones", PY_DOCS + "controlflow.html#defining-functions")]),
    "Módulos y paquetes": (
        "## Idea clave\nUn módulo es un archivo `.py` que puedes importar en otro. Así se organiza un proyecto.\n\n"
        "## Ejemplo\n- `utilidades.py` define `promedio()`.\n- En `main.py`: `from utilidades import promedio`.",
        [("Módulos", PY_DOCS + "modules.html")]),
    "Práctica: biblioteca de utilidades": (
        "## Reto\nCrea un módulo con tres funciones útiles (promedio, máximo y redondeo a dos decimales) y úsalo "
        "desde otro archivo.\n\n## Criterio\nCada función debe tener un ejemplo de uso.",
        []),
}
GENERIC = {
    "DS-201": [("Documentación de pandas", "https://pandas.pydata.org/docs/user_guide/index.html")],
    "ML-301": [("Guía de scikit-learn", "https://scikit-learn.org/stable/user_guide.html")],
    "ATN-100": [],
}


def run(db: Session) -> None:
    rows = db.execute(select(CourseActivity, Course.code).join(CourseUnit, CourseUnit.id == CourseActivity.unit_id)
                      .join(Course, Course.id == CourseUnit.course_id))
    for activity, code in rows:
        if activity.content:
            continue
        if activity.title in LESSONS:
            text, links = LESSONS[activity.title]
            activity.content = text
            activity.resources = [{"title": t, "url": u} for t, u in links]
        else:
            activity.content = (f"## {activity.title}\nContenido DEMO de esta lección. Revisa el recurso recomendado y "
                                f"anota tus dudas para la sesión con tu docente.\n\n## Al terminar\nMarca la actividad "
                                f"como completada.")
            activity.resources = [{"title": t, "url": u} for t, u in GENERIC.get(code, [])]
    db.commit()
