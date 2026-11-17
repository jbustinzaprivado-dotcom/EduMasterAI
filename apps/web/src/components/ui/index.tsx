import { AlertTriangle, Loader2, RotateCw, type LucideIcon } from "lucide-react";
import type { ButtonHTMLAttributes, ReactNode } from "react";
import { ApiError } from "../../lib/api";

export function cx(...classes: (string | false | null | undefined)[]) {
  return classes.filter(Boolean).join(" ");
}

export function Panel({
  title,
  subtitle,
  actions,
  children,
  className,
  glow,
}: {
  title?: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
  glow?: boolean;
}) {
  return (
    <section className={cx("panel flex min-w-0 flex-col p-4 sm:p-5", glow && "panel-glow", className)}>
      {(title || actions) && (
        <header className="mb-4 flex flex-wrap items-start justify-between gap-2">
          <div className="min-w-0">
            {title && <h2 className="text-sm font-semibold tracking-wide text-text">{title}</h2>}
            {subtitle && <p className="mt-0.5 text-xs text-muted">{subtitle}</p>}
          </div>
          {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
        </header>
      )}
      {children}
    </section>
  );
}

type Variant = "primary" | "ghost" | "danger";

export function Button({
  variant = "primary",
  loading,
  icon: Icon,
  children,
  className,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; loading?: boolean; icon?: LucideIcon }) {
  const styles: Record<Variant, string> = {
    primary: "bg-primary text-white hover:bg-[#1a8cf0] shadow-[0_0_18px_-6px_var(--color-primary)]",
    ghost: "border border-line bg-surface-2/40 text-text hover:border-cyan/60 hover:text-cyan",
    danger: "border border-danger/40 bg-danger/10 text-danger hover:bg-danger/20",
  };
  return (
    <button
      className={cx(
        "inline-flex items-center justify-center gap-2 rounded-[10px] px-3.5 py-2 text-sm font-medium transition-colors",
        "disabled:cursor-not-allowed disabled:opacity-50",
        styles[variant],
        className,
      )}
      disabled={loading || props.disabled}
      {...props}
    >
      {loading ? <Loader2 className="size-4 animate-spin" aria-hidden /> : Icon && <Icon className="size-4" aria-hidden />}
      {children}
    </button>
  );
}

const TONES = {
  cyan: "bg-cyan/10 text-cyan border-cyan/30",
  violet: "bg-violet/15 text-[#b593ff] border-violet/35",
  teal: "bg-teal/10 text-teal border-teal/30",
  muted: "bg-surface-2/60 text-muted border-line",
  danger: "bg-danger/10 text-danger border-danger/30",
  warning: "bg-warning/10 text-warning border-warning/30",
} as const;

export function Badge({ tone = "muted", children }: { tone?: keyof typeof TONES; children: ReactNode }) {
  return (
    <span className={cx("inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium", TONES[tone])}>
      {children}
    </span>
  );
}

export function PhaseBadge({ phase }: { phase: number }) {
  return <Badge tone="violet">Fase {phase}</Badge>;
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cx("animate-pulse rounded-lg bg-surface-2/70", className)} aria-hidden />;
}

export function EmptyState({
  icon: Icon,
  title,
  description,
  phase,
}: {
  icon: LucideIcon;
  title: string;
  description: string;
  phase?: number;
}) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-line px-4 py-8 text-center">
      <Icon className="size-7 text-primary/70" aria-hidden />
      <p className="text-sm font-medium text-text">{title}</p>
      <p className="max-w-xs text-xs text-muted">{description}</p>
      {phase !== undefined && <PhaseBadge phase={phase} />}
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const message = error instanceof Error ? error.message : "No se pudo cargar la información.";
  const cid = error instanceof ApiError ? error.body.correlation_id : null;
  return (
    <div role="alert" className="flex flex-col items-center gap-2 rounded-xl border border-danger/30 bg-danger/5 px-4 py-6 text-center">
      <AlertTriangle className="size-6 text-danger" aria-hidden />
      <p className="text-sm text-text">{message}</p>
      {cid && <p className="font-mono text-[11px] text-muted">correlation_id: {cid}</p>}
      {onRetry && (
        <Button variant="ghost" icon={RotateCw} onClick={onRetry}>
          Reintentar
        </Button>
      )}
    </div>
  );
}

export function PageHeader({ title, description, actions }: { title: string; description?: string; actions?: ReactNode }) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-xl font-semibold tracking-tight sm:text-2xl">{title}</h1>
        {description && <p className="mt-1 text-sm text-muted">{description}</p>}
      </div>
      {actions}
    </div>
  );
}

export function DemoTag({ children = "DEMO" }: { children?: ReactNode }) {
  return <Badge tone="warning">{children}</Badge>;
}
