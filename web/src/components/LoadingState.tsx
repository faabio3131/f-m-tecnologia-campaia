import styles from "./LoadingState.module.css";

export interface LoadingStateProps {
  label?: string;
}

/**
 * WP-03: standardized "carregando" state for the authenticated shell. `role="status"` +
 * `aria-live="polite"` so assistive tech announces the loading state without stealing
 * focus -- never a silent blank screen while a Server Component awaits the BFF.
 */
export function LoadingState({ label = "Carregando…" }: LoadingStateProps) {
  return (
    <div className={styles.loading} role="status" aria-live="polite">
      <span className={styles.spinner} aria-hidden="true" />
      <span>{label}</span>
    </div>
  );
}
