import "vitest";

interface JestAxeMatchers<R = unknown> {
  toHaveNoViolations(): R;
}

// Ambient module augmentation via declaration merging: these interfaces
// intentionally declare no members of their own beyond `extends`, which
// is how TypeScript merges jest-axe's matcher into Vitest's `expect`.
/* eslint-disable @typescript-eslint/no-empty-object-type */
declare module "vitest" {
  interface Assertion<T = unknown> extends JestAxeMatchers<T> {}
  interface AsymmetricMatchersContaining extends JestAxeMatchers {}
}
/* eslint-enable @typescript-eslint/no-empty-object-type */
