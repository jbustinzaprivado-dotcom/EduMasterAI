const dateTime = new Intl.DateTimeFormat("es-PE", { dateStyle: "short", timeStyle: "short" });
const time = new Intl.DateTimeFormat("es-PE", { timeStyle: "short" });
const number = new Intl.NumberFormat("es-PE");

export const formatDateTime = (iso: string | null | undefined) => (iso ? dateTime.format(new Date(iso)) : "—");
export const formatTime = (iso: string) => time.format(new Date(iso));
export const formatNumber = (n: number) => number.format(n);

/** Variación porcentual frente al periodo comparable; null si no hay base para comparar. */
export function variation(value: number, previous: number | null): number | null {
  if (previous === null || previous === 0) return null;
  return Math.round(((value - previous) / previous) * 100);
}

export function relativeTime(iso: string, now = Date.now()): string {
  const seconds = Math.round((now - new Date(iso).getTime()) / 1000);
  if (seconds < 60) return "hace un momento";
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `hace ${minutes} min`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `hace ${hours} h`;
  return formatDateTime(iso);
}
