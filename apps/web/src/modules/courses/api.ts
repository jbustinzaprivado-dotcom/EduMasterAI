import { api } from "../../lib/api";

export interface Activity {
  id: string;
  position: number;
  title: string;
  kind: "lectura" | "video" | "practica";
  estimated_minutes: number;
  required: boolean;
}

export interface Unit {
  id: string;
  position: number;
  title: string;
  activities: Activity[];
}

export interface Course {
  id: string;
  code: string;
  title: string;
  description: string;
  level: string;
  status: "draft" | "published" | "archived";
  unit_count: number;
  activity_count: number;
  offering_count: number;
  units: Unit[] | null;
}

export interface Offering {
  id: string;
  course_id: string;
  course_code: string;
  course_title: string;
  course_level: string;
  instructor_id: string;
  instructor_name: string;
  period: string;
  cohort: string;
  starts_on: string;
  ends_on: string;
  status: string;
  enrolled: number;
  completed: number;
  avg_progress: number | null;
  my_enrollment: { id: string; status: string; progress: number; completed_activity_ids: string[] } | null;
  can_manage: boolean;
  units: Unit[] | null;
}

export interface RosterRow {
  enrollment_id: string;
  student_id: string;
  student_name: string;
  student_email: string;
  status: string;
  progress: number;
  last_activity_at: string | null;
  grade: number | null;
  graded_weight: number;
}

export interface Assessment {
  id: string;
  offering_id: string;
  course_title: string;
  cohort: string;
  title: string;
  kind: string;
  instructions: string;
  max_score: number;
  weight: number;
  due_at: string;
  max_attempts: number;
  submissions: number | null;
  graded: number | null;
  mine: { attempts: number; last_submitted_at: string | null; best_score: number | null; feedback: string | null } | null;
  can_manage: boolean;
}

export interface Attempt {
  id: string;
  assessment_id: string;
  student_id: string;
  student_name: string;
  attempt_no: number;
  answer: string;
  submitted_at: string;
  late: boolean;
  score: number | null;
  feedback: string | null;
  graded_at: string | null;
}

export const LEVEL_LABEL: Record<string, string> = { basico: "Básico", intermedio: "Intermedio", avanzado: "Avanzado" };
export const KIND_LABEL: Record<string, string> = {
  lectura: "Lectura", video: "Video", practica: "Práctica",
  opcion_multiple: "Opción múltiple", verdadero_falso: "Verdadero/Falso", respuesta_corta: "Respuesta corta",
  archivo: "Entrega de archivo",
};
export const STATUS_LABEL: Record<string, string> = {
  draft: "Borrador", published: "Publicado", archived: "Archivado",
  active: "En curso", completed: "Completado", dropped: "Retirado", planned: "Planificada", closed: "Cerrada",
};

export function sendEvent(offeringId: string, eventType: string, activityId?: string, durationSeconds = 0) {
  return api<{ duplicate: boolean; progress: number; enrollment_status: string }>("/learning-events", {
    method: "POST",
    body: JSON.stringify({
      event_id: crypto.randomUUID(), // idempotencia: reenviar el mismo evento no lo duplica
      offering_id: offeringId,
      activity_id: activityId,
      event_type: eventType,
      duration_seconds: durationSeconds,
      occurred_at: new Date().toISOString(),
    }),
  });
}
