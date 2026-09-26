import styles from "./StatusPanel.module.css";

export interface StatusPanelItem {
  label: string;
  value: string;
}

export interface StatusPanelProps {
  title: string;
  items: StatusPanelItem[];
}

function slugify(title: string): string {
  return title
    .toLowerCase()
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "");
}

export function StatusPanel({ title, items }: StatusPanelProps) {
  const headingId = `status-panel-${slugify(title)}-heading`;

  return (
    <section className={styles.panel} aria-labelledby={headingId}>
      <h2 id={headingId} className={styles.heading}>
        {title}
      </h2>
      <dl className={styles.list}>
        {items.map((item) => (
          <div className={styles.row} key={item.label}>
            <dt className={styles.term}>{item.label}</dt>
            <dd className={styles.definition}>{item.value}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
