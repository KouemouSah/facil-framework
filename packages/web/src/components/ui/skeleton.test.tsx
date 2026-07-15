import React from "react";
import { describe, it, expect } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { Skeleton } from "./skeleton";

describe("Skeleton", () => {
  it("renders a pulsing, aria-hidden placeholder and merges className", () => {
    const html = renderToStaticMarkup(<Skeleton className="h-4 w-20" />);
    expect(html).toContain("animate-pulse");
    expect(html).toContain("h-4 w-20");
    expect(html).toContain('aria-hidden');
    expect(html).toContain('data-testid="skeleton"');
  });
});
