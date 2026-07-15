import * as React from "react";
import { describe, it, expect, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { Card, CardContent, CardSkeleton } from "./card";
import { DetailPanel, DetailPanelSkeleton } from "./detail-panel";
import { RecordSurface, RecordSurfaceSkeleton } from "@/components/shared/record-surface";

// RecordSurface calls useTranslations("common"), which requires a
// NextIntlClientProvider at runtime. This test only exercises the loading
// vs. children branch (pure layout), so a minimal key-echo mock is enough.
vi.mock("next-intl", () => ({
  useTranslations: () => (key: string) => key,
}));

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

describe("Card loading prop", () => {
  it("loading renders a skeleton and not the children", () => {
    const html = renderToStaticMarkup(
      <Card loading>
        <CardContent>real-children-marker</CardContent>
      </Card>,
    );
    expect(html).toContain('data-testid="skeleton"');
    expect(html).not.toContain("real-children-marker");
  });

  it("without loading renders the children and no skeleton", () => {
    const html = renderToStaticMarkup(
      <Card>
        <CardContent>real-children-marker</CardContent>
      </Card>,
    );
    expect(html).toContain("real-children-marker");
    expect(html).not.toContain('data-testid="skeleton"');
  });
});

describe("RecordSurface loading prop", () => {
  const noop = () => {};

  it("loading renders a skeleton and not the children", () => {
    const html = renderToStaticMarkup(
      <RecordSurface title="Title" onClose={noop} resourceKey="test-resource">
        <div>real-children-marker</div>
      </RecordSurface>,
    );
    // Without loading, sanity check first (children present).
    expect(html).toContain("real-children-marker");

    const loadingHtml = renderToStaticMarkup(
      <RecordSurface title="Title" onClose={noop} resourceKey="test-resource" loading>
        <div>real-children-marker</div>
      </RecordSurface>,
    );
    expect(loadingHtml).toContain('data-testid="skeleton"');
    expect(loadingHtml).not.toContain("real-children-marker");
  });

  it("without loading renders the children and no skeleton", () => {
    const html = renderToStaticMarkup(
      <RecordSurface title="Title" onClose={noop} resourceKey="test-resource">
        <div>real-children-marker</div>
      </RecordSurface>,
    );
    expect(html).toContain("real-children-marker");
    expect(html).not.toContain('data-testid="skeleton"');
  });
});

describe("DetailPanel loading prop", () => {
  const noop = () => {};

  it("loading renders a skeleton and not the children", () => {
    const html = renderToStaticMarkup(
      <DetailPanel title="Title" onClose={noop} loading>
        <div>real-children-marker</div>
      </DetailPanel>,
    );
    expect(html).toContain('data-testid="skeleton"');
    expect(html).not.toContain("real-children-marker");
  });

  it("without loading renders the children and no skeleton", () => {
    const html = renderToStaticMarkup(
      <DetailPanel title="Title" onClose={noop}>
        <div>real-children-marker</div>
      </DetailPanel>,
    );
    expect(html).toContain("real-children-marker");
    expect(html).not.toContain('data-testid="skeleton"');
  });
});
