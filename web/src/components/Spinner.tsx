import styles from "./Spinner.module.css";

export interface SpinnerProps {
  label?: string;
}

export function Spinner({ label = "Carregando" }: SpinnerProps) {
  return (
    <div className={styles.wrapper} role="status">
      <span className={styles.spinner} aria-hidden="true" />
      <span className={styles.visuallyHidden}>{label}</span>
    </div>
  );
}
