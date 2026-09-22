import styles from "./EmptyState.module.css";

export interface EmptyStateProps {
  title: string;
  description?: string;
}

/** WP-03: standardized "vazio" state for the authenticated shell -- no error occurred,
 * there is simply nothing to show yet (e.g. no business feature built on this tenant's
 * shell before WP-04). */
export function EmptyState({ title, description }: EmptyStateProps) {
  return (
    <div className={styles.empty}>
      <p className={styles.title}>{title}</p>
      {description ? <p className={styles.description}>{description}</p> : null}
    </div>
  );
}
