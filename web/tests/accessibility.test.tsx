import { render } from "@testing-library/react";
import { axe } from "jest-axe";
import { describe, expect, it } from "vitest";
import FoundationPage from "@/app/page";

describe("FoundationPage accessibility baseline", () => {
  it("has no detectable automated accessibility violations", async () => {
    const { container } = render(<FoundationPage />);
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });
});
