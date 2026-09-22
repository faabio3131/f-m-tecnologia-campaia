import type { HTMLAttributes } from "react";
import styles from "./Badge.module.css";

type BadgeTone = "neutral" | "accent" | "warning";

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: BadgeTone;
}

export function Badge({ tone = "neutral", className, ...rest }: BadgeProps) {
  const toneClass =
    tone === "accent"
      ? styles.accent
      : tone === "warning"
        ? styles.warning
        : styles.neutral;
  const classes = [styles.badge, toneClass, className]
    .filter(Boolean)
    .join(" ");
  return <span className={classes} {...rest} />;
}
