import type { ReactNode } from "react";
import styles from "./ErrorState.module.css";

export interface ErrorStateProps {
  title: string;
  description?: string;
  action?: ReactNode;
}

/** Mensagem de erro para o usuario final -- nunca stack trace, secret, token ou
 * detalhe interno (Etapa 2, secao 27). */
export function ErrorState({ title, description, action }: ErrorStateProps) {
  return (
    <div className={styles.wrapper} role="alert">
      <h3 className={styles.title}>{title}</h3>
      {description ? <p className={styles.description}>{description}</p> : null}
      {action ? <div className={styles.action}>{action}</div> : null}
    </div>
  );
}
