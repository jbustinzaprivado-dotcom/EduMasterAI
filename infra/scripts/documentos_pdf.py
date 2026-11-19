"""Genera los PDF de la documentación con capturas del sistema (docs/pdf).

  1. EduMaster_AI_Documentacion_Sistema.pdf: presentación, despliegue y operación, módulos (con capturas),
     seguridad, pruebas de carga y acta de aceptación.
  2. EduMaster_AI_Informe_Desarrollo.pdf: resumen ejecutivo, capturas principales, bitácora, backlog,
     decisiones, mapa de procesos y glosario.

Requisitos: `pip install markdown` y Microsoft Edge (o Chrome) para imprimir a PDF.
Las capturas se regeneran con `node scripts/capturas.mjs` (en apps/web) sobre la API aislada de pruebas.
Uso (desde la raíz):  python infra/scripts/documentos_pdf.py
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
SHOTS = DOCS / "capturas"
OUT = DOCS / "pdf"

# Capturas que acompañan a cada módulo de docs/modulos.md (por número de sección).
FIGURES: dict[int, list[tuple[str, str]]] = {
    1: [("01-login", "Inicio de sesión con código de institución, correo y contraseña.")],
    2: [("23-usuarios-roles", "Administración de usuarios y roles de la institución.")],
    3: [("22-auditoria", "Bitácora de auditoría: quién hizo qué y cuándo.")],
    4: [("07-cursos-docente", "Catálogo de cursos visto por el docente."),
        ("10-leccion", "Lección con contenido con formato, recursos y versión.")],
    6: [("11-evaluaciones-docente", "Evaluaciones del docente: entregas y calificación.")],
    7: [("14-rutas-coordinacion", "Ruta «Analista de datos junior» vista por la coordinación."),
        ("18-ruta-estudiante", "La misma ruta vista por la estudiante: etapas bloqueadas hasta cumplir la anterior.")],
    8: [("02-dashboard-admin", "Panel de la administración: red neuronal etiquetada, indicadores, progreso, mapa, "
         "finalización, habilidades, actividad y hoja de ruta."),
        ("16-dashboard-estudiante", "Panel personal de la estudiante."),
        ("25-movil-estudiante", "El mismo panel en un teléfono (390 px).")],
    9: [("19-notificaciones", "Notificaciones en vivo (SSE) en la campana.")],
    10: [("20-certificados", "Certificados emitidos automáticamente, con folio y PDF."),
         ("21-verificacion-publica", "Verificación pública sin sesión: solo datos mínimos.")],
    11: [("13-comunidad", "Comunidad del curso: anuncios y debates con moderación.")],
    12: [("15-analitica", "Analítica con indicadores definidos, filtros y exportación auditada.")],
    13: [("12-habilidades-heatmap", "Mapa de calor de competencias: nivel estimado y validado.")],
    14: [("03-modelo-candidato", "Model card: comparación con baselines, segmentos, calibración y limitaciones.")],
    15: [("04-modelo-confirmar-aprobacion", "Aprobación humana antes de publicar el modelo en la institución."),
         ("08-oferta-riesgo-ia", "Riesgo de abandono por estudiante en la oferta del docente."),
         ("09-alerta-factores", "Alerta con los factores que la explican; el docente la atiende o descarta.")],
    16: [("17-ia-tutor", "IA Tutor: «¿Qué hago ahora?» con motivo e impacto esperado.")],
    17: [("06-red-neuronal", "Visualizador de la arquitectura con el modelo publicado y el inspector de capa.")],
    18: [("24-operacion", "Pantalla de Operación: latencia, errores y conexiones frente a los objetivos de §10.5.")],
}

CSS = """
@page { size: A4; margin: 18mm 16mm 20mm 16mm;
  @bottom-right { content: counter(page) " / " counter(pages); font: 9pt Inter, Segoe UI, sans-serif; color: #6b7a90; }
  @bottom-left { content: "EduMaster.ai · %(title)s"; font: 9pt Inter, Segoe UI, sans-serif; color: #6b7a90; } }
@page :first { @bottom-right { content: none; } @bottom-left { content: none; } }
* { box-sizing: border-box; }
body { font: 10.5pt/1.5 "Segoe UI", Inter, Arial, sans-serif; color: #12233d; margin: 0; }
h1 { font-size: 21pt; color: #06152b; border-bottom: 3px solid #087fe5; padding-bottom: 4px; margin: 0 0 12px;
     break-before: page; }
h2 { font-size: 14pt; color: #087fe5; margin: 20px 0 6px; break-after: avoid; }
h3 { font-size: 12pt; color: #06152b; margin: 14px 0 4px; break-after: avoid; }
p, li { orphans: 3; widows: 3; }
a { color: #087fe5; text-decoration: none; }
code { font-family: Consolas, monospace; font-size: 9pt; background: #eef3fa; padding: 1px 4px; border-radius: 3px; }
pre { background: #0b1e3a; color: #dfe9f7; padding: 8px 10px; border-radius: 6px; white-space: pre-wrap;
      font-size: 8.8pt; break-inside: avoid; }
pre code { background: none; color: inherit; padding: 0; }
table { border-collapse: collapse; width: 100%%; margin: 8px 0 12px; font-size: 9pt; break-inside: auto; }
th { background: #06152b; color: #fff; text-align: left; padding: 5px 6px; }
td { border-bottom: 1px solid #d9e2ef; padding: 4px 6px; vertical-align: top; }
tr { break-inside: avoid; }
hr { border: 0; border-top: 1px solid #d9e2ef; margin: 16px 0; }
figure { margin: 10px 0 16px; break-inside: avoid; text-align: center; }
figure.movil img { max-height: 150mm; border: 1px solid #c8d4e6; border-radius: 6px; }
.slice { width: 100%%; overflow: hidden; border: 1px solid #c8d4e6; border-radius: 6px; }
.slice img { display: block; width: 100%%; }
figcaption { font-size: 9pt; color: #4b5d78; margin-top: 4px; }
.cover { height: 252mm; display: flex; flex-direction: column; justify-content: center; padding: 0 12mm;
         background: linear-gradient(160deg, #06152b 0%%, #0b2c58 60%%, #087fe5 140%%); color: #fff;
         border-radius: 10px; }
.cover h1 { border: 0; color: #fff; font-size: 34pt; break-before: avoid; margin: 0; }
.cover .brand span { color: #20c8f5; }
.cover .sub { font-size: 15pt; color: #cfe3ff; margin: 6px 0 26px; }
.cover .meta { font-size: 10.5pt; color: #9fb8db; line-height: 1.8; }
.cover-shot { margin-top: 24px; border-color: #2a4a7a; }
.toc { break-before: page; }
.toc h1 { break-before: avoid; }
.toc ol { padding-left: 18px; } .toc li { margin: 2px 0; } .toc ul { margin: 2px 0 6px; font-size: 9.5pt; }
.note { background: #eef6ff; border-left: 4px solid #087fe5; padding: 8px 12px; border-radius: 4px; margin: 10px 0; }
"""


def md(text: str) -> str:
    return markdown.markdown(text, extensions=["tables", "fenced_code", "toc", "sane_lists"])


def clean(text: str) -> str:
    """Quita los enlaces a otros .md (en el PDF no navegan) y conserva el texto."""
    text = re.sub(r"\[([^\]]+)\]\((?!https?:)[^)]*\)", r"\1", text)
    return text


def jpeg_size(path: Path) -> tuple[int, int]:
    """Ancho y alto de un JPEG leyendo su cabecera (sin librerías de imagen)."""
    data = path.read_bytes()
    i = 2
    while i < len(data):
        marker, length = data[i + 1], int.from_bytes(data[i + 2:i + 4], "big")
        if marker in (0xC0, 0xC1, 0xC2):
            return int.from_bytes(data[i + 7:i + 9], "big"), int.from_bytes(data[i + 5:i + 7], "big")
        i += 2 + length
    raise ValueError(f"No se pudo leer el tamaño de {path.name}")


SLICE = 1.15  # alto/ancho máximo de cada tramo: cabe en una página A4 a ancho completo y se lee bien


def figure(name: str, caption: str) -> str:
    """Una captura. Si es más alta que una página, se parte en tramos legibles a ancho completo (con CSS)."""
    path = SHOTS / f"{name}.jpg"
    uri = path.resolve().as_uri()
    if "movil" in name:
        return f'\n\n<figure class="movil"><img src="{uri}" alt="{caption}"><figcaption>{caption}</figcaption></figure>\n\n'
    w, h = jpeg_size(path)
    step = int(w * SLICE)
    n = max(1, -(-h // step))
    if n > 1 and h - (n - 1) * step < w * 0.25:  # un último tramo diminuto se suma al anterior
        n -= 1
    blocks = []
    for k in range(n):
        part_h = (h - k * step) if k == n - 1 else step
        label = f"{caption} (parte {k + 1} de {n})" if n > 1 else caption
        blocks.append(
            f'<figure><div class="slice" style="aspect-ratio:{w}/{part_h}">'
            f'<img src="{uri}" alt="{caption}" style="transform:translateY(-{100 * k * step / h:.4f}%)"></div>'
            f'<figcaption>{label}</figcaption></figure>')
    return "\n\n" + "".join(blocks) + "\n\n"


def read(rel: str) -> str:
    return clean((DOCS / rel).read_text(encoding="utf-8"))


def modules_with_figures() -> str:
    text = read("modulos.md")
    parts = re.split(r"(?m)^(?=## \d+\. )", text)
    out = [parts[0].split("\n", 1)[1]]  # sin el título del archivo
    for part in parts[1:]:
        n = int(re.match(r"## (\d+)\.", part).group(1))
        body = part.rstrip().removesuffix("---").rstrip()
        figs = "".join(figure(f, c) for f, c in FIGURES.get(n, []))
        out.append(body + figs + "\n\n---\n\n")
    return "".join(out)


def readme_body() -> str:
    text = clean((ROOT / "README.md").read_text(encoding="utf-8"))
    start = text.index("## Qué funciona hoy")
    return text[start:]


def toc(chapters: list[tuple[str, str, str]]) -> str:
    items = []
    for title, anchor, html in chapters:
        subs = re.findall(r"<h2[^>]*>(.*?)</h2>", html)
        sub = "".join(f"<li>{re.sub('<[^>]+>', '', s)}</li>" for s in subs[:24])
        items.append(f'<li><b>{title}</b>{f"<ul>{sub}</ul>" if sub else ""}</li>')
    return f'<section class="toc"><h1>Contenido</h1><ol>{"".join(items)}</ol></section>'


def cover(title: str, subtitle: str, shot: str) -> str:
    uri = (SHOTS / f"{shot}.jpg").resolve().as_uri()
    return f"""<section class="cover">
  <div class="brand" style="font-size:13pt;letter-spacing:.2em;color:#9fb8db">APRENDE · PRACTICA · DESTACA</div>
  <h1 class="brand">EduMaster<span>.ai</span></h1>
  <div class="sub">{title}<br><span style="font-size:11.5pt">{subtitle}</span></div>
  <div class="meta">Plataforma de aprendizaje inteligente · proyecto académico grupal<br>
  Repositorio: github.com/jbustinzaprivado-dotcom/EduMasterAI<br>
  Generado el {date.today().strftime('%d/%m/%Y')} · datos de instituciones DEMO (sintéticos)</div>
  <div class="slice cover-shot" style="aspect-ratio:16/9"><img src="{uri}" alt="Panel de EduMaster.ai"></div>
</section>"""


def page(title: str, short: str, body: str) -> str:
    return (f'<!doctype html><html lang="es"><head><meta charset="utf-8"><title>{title}</title>'
            f'<style>{CSS % {"title": short}}</style></head><body>{body}</body></html>')


def build(name: str, title: str, short: str, subtitle: str, shot: str,
          chapters: list[tuple[str, str, str]], intro: str = "") -> Path:
    body = cover(title, subtitle, shot) + toc(chapters) + intro + "".join(
        f'<h1 id="{a}">{t}</h1>' + h for t, a, h in chapters)
    OUT.mkdir(parents=True, exist_ok=True)
    html = OUT / f"{name}.html"
    html.write_text(page(title, short, body), encoding="utf-8")
    pdf = OUT / f"{name}.pdf"
    browser = next((p for p in (
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        shutil.which("msedge") or "", shutil.which("chromium") or "", shutil.which("google-chrome") or "",
    ) if p and Path(p).exists()), None)
    if not browser:
        sys.exit("No se encontró Edge ni Chrome para imprimir el PDF.")
    subprocess.run([browser, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                    "--allow-file-access-from-files", "--virtual-time-budget=8000",
                    f"--print-to-pdf={pdf}", html.resolve().as_uri()], check=True, capture_output=True)
    html.unlink()
    return pdf


def body_of(title_anchor_md: list[tuple[str, str, str]]) -> list[tuple[str, str, str]]:
    out = []
    for title, anchor, text in title_anchor_md:
        text = re.sub(r"^# (.+)$", r"## \1", text, flags=re.M)
        out.append((title, anchor, md(text)))
    return out


def main() -> None:
    missing = [f for figs in FIGURES.values() for f, _ in figs if not (SHOTS / f"{f}.jpg").exists()]
    if missing:
        sys.exit(f"Faltan capturas en docs/capturas: {missing}. Ejecuta apps/web/scripts/capturas.mjs.")

    sistema = body_of([
        ("Presentación del sistema", "presentacion", readme_body()),
        ("Despliegue y operación", "despliegue", read("runbooks.md")),
        ("Módulos: funcionamiento y decisiones", "modulos", modules_with_figures()),
        ("Seguridad", "seguridad", read("fase-7/seguridad.md")),
        ("Pruebas de carga · escenario aula", "carga-aula", read("fase-7/carga-aula.md")),
        ("Pruebas de carga · escenario estrés", "carga-estres", read("fase-7/carga-estres.md")),
        ("Acta de aceptación (UAT)", "uat", read("fase-7/aceptacion-uat.md")),
    ])
    a = build("EduMaster_AI_Documentacion_Sistema", "Documentación del sistema", "Documentación del sistema",
              "Despliegue, módulos con capturas, seguridad y aceptación", "02-dashboard-admin", sistema)

    resumen = """
<div class="note">EduMaster.ai es una plataforma de aprendizaje con IA construida según el Documento Maestro
(especificación funcional y técnica v1.0) y su manual de procedimientos, siguiendo las fases 0 a 8 del §14.</div>

| Aspecto | Resultado |
|---|---|
| Periodo | Propuesto el 12-11-2026 · desarrollo del 17-11 al 19-11-2026 · exposición el 19-11-2026 |
| Fases del §14 | 0 a 8 completas (ver backlog). Pendientes no bloqueantes: escaneo de dependencias en la CI y ranking aprendido (cabeza D) |
| Arquitectura | Monolito modular: FastAPI + SQLAlchemy/Alembic, React 19 + TypeScript, PyTorch para entrenar y NumPy para predecir |
| Despliegue | PC propio + Cloudflare Tunnel (HTTPS público), smoke test previo, respaldo cifrado y runbooks |
| IA | Riesgo de abandono con red multitarea GRU calibrada (ROC-AUC 0,866 en prueba), aprobación humana por institución y rollback |
| Calidad | 89 pruebas de API, 5 de ML, 8 de web y 20 recorridos E2E con Playwright; CI con 4 trabajos en cada cambio |
| Seguridad | OAuth2 con renovación rotatoria, RBAC/ABAC, aislamiento multi-institución, OWASP Top 10, cabeceras CSP/HSTS |
| Rendimiento | Aula de 40 personas: dashboard p95 0,9 s (objetivo 2,5 s), inferencia 0,25 s (objetivo 0,8 s) |
| Decisiones | 46 decisiones registradas (D01-D46), cada una con la sección del documento que la respalda |

### Hallazgos de las pruebas en entorno real (19-11-2026)

1. **Prueba de carga:** el pool de conexiones (15) era menor que los hilos de la API (40); con carga la plataforma se
   congelaba. Se alineó y ahora soporta 70 peticiones por segundo sin errores (D43).
2. **Simulación de un día de clases:** el límite de inicio de sesión por IP bloqueaba a la persona 11 de un aula que
   comparte Wi-Fi; ahora es por IP + correo (D46). El resumen del docente contaba totales de toda la institución.
3. **Revisión visual con capturas:** las acciones automáticas aparecían como «Usuario no identificado»; ahora se
   distinguen del sistema y de intentos de acceso.
"""
    principales = "".join(figure(f, c) for f, c in [
        ("02-dashboard-admin", "Panel de la administración."),
        ("05-modelo-publicado", "Modelo publicado tras la aprobación humana."),
        ("08-oferta-riesgo-ia", "Riesgo de abandono en la oferta del docente."),
        ("17-ia-tutor", "IA Tutor del estudiante."),
    ])
    informe = body_of([
        ("Resumen ejecutivo", "resumen", resumen),
        ("Capturas principales", "capturas", principales),
        ("Bitácora de desarrollo", "bitacora", read("bitacora.md")),
        ("Backlog y estado por fase", "backlog", read("fase-0/backlog.md")),
        ("Registro de decisiones", "decisiones", read("fase-0/decisiones.md")),
        ("Mapa de procesos", "procesos", read("fase-0/mapa-de-procesos.md")),
        ("Glosario", "glosario", read("fase-0/glosario.md")),
    ])
    b = build("EduMaster_AI_Informe_Desarrollo", "Informe de desarrollo", "Informe de desarrollo",
              "Fases 0 a 8 · bitácora, decisiones y resultados", "05-modelo-publicado", informe)
    for p in (a, b):
        print(f"{p}  ({p.stat().st_size / 1_000_000:.1f} MB)")


if __name__ == "__main__":
    main()
