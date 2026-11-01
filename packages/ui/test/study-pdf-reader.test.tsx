import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import type { StudyContracts as W } from "@jana/client-core";
import { StudyPdfReader } from "../src/learn/StudyPdfReader.js";
afterEach(cleanup);
const chunks = Array.from({ length: 69 }, (_, i) => ({ chunk_id: `sck_${String(i).padStart(26, "0")}`, source_id: `src_${"0".repeat(26)}`, revision: 1, ordinal: i, text: `Page ${i + 1}: literal ||w||22`, locator: { kind: "page", page: i + 1 } })) as W.Chunk[];
const base = { chunks, page: 14, image: { url: "blob:page14", page: 14 }, loading: false, failed: false, citation: null, onPage: vi.fn() };
test("a long PDF exposes only the selected original page and keeps extracted evidence literal", () => {
  const { container } = render(<StudyPdfReader {...base} />);
  expect(screen.getByRole("img", { name: "Source page 14" })).toBeTruthy();
  expect(container.querySelectorAll("img")).toHaveLength(1);
  expect(screen.queryByText("Page 15: literal ||w||22")).toBeNull();
  fireEvent.click(screen.getByText("Read extracted passage"));
  expect(screen.getByText("Page 14: literal ||w||22")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Next", exact: true }));
  expect(base.onPage).toHaveBeenLastCalledWith(chunks[14]);
  fireEvent.change(screen.getByRole("combobox", { name: "Page", exact: true }), { target: { value: "16" } });
  expect(base.onPage).toHaveBeenLastCalledWith(chunks[15]);
});
test("a failed original page remains retryable and cited evidence stays exact", () => {
  const citation = { source_id: chunks[13]!.source_id, revision: 1, chunk_id: chunks[13]!.chunk_id, start: 17, end: 24, quote: "||w||22" };
  const { container } = render(<StudyPdfReader {...base} image={null} failed citation={citation} />);
  expect(container.querySelector("mark")?.textContent).toBe("||w||22");
  fireEvent.click(screen.getByRole("button", { name: "View source page 14" }));
  expect(base.onPage).toHaveBeenLastCalledWith(chunks[13]);
});
