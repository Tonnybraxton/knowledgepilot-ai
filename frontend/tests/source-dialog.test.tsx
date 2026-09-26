import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";
import { SourceDialog } from "@/components/chat/source-dialog";
import type { Citation } from "@/types/api";

const source: Citation = { citation_number: 1, document_id: "document-id", chunk_id: "chunk-id", document_name: "orion.pdf", excerpt: "Orion has 80 kWh capacity.", page_number: 2, section_title: null };

it("shows source provenance and links to the exact passage and authorized download", async () => {
  const close = vi.fn();
  render(<SourceDialog source={source} onClose={close} />);
  expect(screen.getByRole("dialog", { name: "orion.pdf" })).toBeVisible();
  expect(screen.getByText("Source [1] · Page 2")).toBeVisible();
  expect(screen.getByRole("link", { name: "Inspect document" })).toHaveAttribute("href", "/app/documents/document-id?chunk=chunk-id");
  expect(screen.getByRole("link", { name: "Download original" })).toHaveAttribute("href", "/api/v1/documents/document-id/source");
  await userEvent.keyboard("{Escape}");
  expect(close).toHaveBeenCalledOnce();
});

it("preserves deleted-source excerpts without presenting broken download links", () => {
  render(<SourceDialog source={{ ...source, document_id: null, chunk_id: null }} onClose={vi.fn()} />);
  expect(screen.getByText(source.excerpt)).toBeVisible();
  expect(screen.getByRole("status")).toHaveTextContent("has been deleted");
  expect(screen.queryByRole("link")).not.toBeInTheDocument();
});
