import styles from "./ErrorState.module.css";

export interface ErrorStateProps {
  title: string;
  description?: string;
}

/** WP-03: standardized "erro" state for the authenticated shell. `role="alert"`. */
export function ErrorState({ title, description }: ErrorStateProps) {
  return (
    <div className={styles.error} role="alert">
      <p className={styles.title}>{title}</p>
      {description ? <p className={styles.description}>{description}</p> : null}
    </div>
  );
}
