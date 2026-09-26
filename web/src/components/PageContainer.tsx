import type { HTMLAttributes } from "react";
import styles from "./PageContainer.module.css";

export function PageContainer({
  className,
  ...rest
}: HTMLAttributes<HTMLDivElement>) {
  const classes = [styles.container, className].filter(Boolean).join(" ");
  return <div className={classes} {...rest} />;
}
