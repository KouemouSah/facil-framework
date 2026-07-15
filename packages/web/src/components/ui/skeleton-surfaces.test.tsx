import * as React from "react";
import { describe, it, expect } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { CardSkeleton } from "./card";
import { DetailPanelSkeleton } from "./detail-panel";
import { RecordSurfaceSkeleton } from "@/components/shared/record-surface";

describe("shared surfaces expose a DRY loading skeleton", () => {
  it("CardSkeleton renders Skeleton placeholders", () => {
    expect(renderToStaticMarkup(<CardSkeleton />)).toContain('data-testid="skeleton"');
  });

  it("DetailPanelSkeleton renders Skeleton placeholders", () => {
    expect(renderToStaticMarkup(<DetailPanelSkeleton />)).toContain('data-testid="skeleton"');
  });

  it("RecordSurfaceSkeleton renders Skeleton placeholders", () => {
    expect(renderToStaticMarkup(<RecordSurfaceSkeleton />)).toContain('data-testid="skeleton"');
  });
});
