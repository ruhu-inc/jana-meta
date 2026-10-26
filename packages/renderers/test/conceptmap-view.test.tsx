// The concept map's drawing (UXS-22 map view, DSN-23): on the real Physics backbone every box says its state in words
// as well as its fill, the learner's badges in words, a linked skill its subject; one box is in the tab order; a lit
// gap path rings its boxes and links and dims the rest; motion only without reduced motion; arrow keys move along the
// column and the links; titles wrap to two lines with an ellipsis.
import fs from "node:fs";
import path from "node:path";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { ConceptMapSvg, layoutOf, moveFrom, wrap, type DrawEdge, type DrawNode } from "../src/conceptmap/ConceptMapSvg.js";
import { FIXTURES, t } from "./helpers.js";

const raw = JSON.parse(fs.readFileSync(path.join(FIXTURES, "concept-map", "phy.json"), "utf8")) as { nodes: { id: string; code: string; linked: boolean }[]; edges: DrawEdge[] };
const VT = "kc.phy.o.motion.velocity_time_gradient";
const GRADIENT = "kc.mth.o.coordinate_geometry.gradient";
const nodes: DrawNode[] = raw.nodes.map((n) => ({
  id: n.id, code: n.code, title: `Skill ${n.id.split(".").pop()!.replaceAll("_", " ")}`, state: n.id === VT ? "explaining" : "not_started",
  stateWord: n.id === VT ? "Explaining it back" : "Not started", linked: n.linked, ...(n.linked ? { subject: "Maths" } : {}),
  asked: n.id === VT ? 3 : 0, mistakes: n.id === VT ? 1 : 0, next: n.id === VT ? 1 : 0,
}));
const edges: DrawEdge[] = raw.edges.map((e) => ({ ...e, ...(e.kind === "root_gap" ? { reviewed: false, name: "Acceleration from a single point" } : { strength: "required" as const }) }));

describe("concept map drawing", () => {
  it("states in words, badges in words, one box in the tab order", () => {
    const html = renderToStaticMarkup(<ConceptMapSvg nodes={nodes} edges={edges} label="Physics map" t={t} active={VT} reducedMotion={true} onActivate={() => undefined} onFocusNode={() => undefined} />);
    expect((html.match(/data-kc-node=/g) ?? []).length).toBe(nodes.length);
    expect((html.match(/tabindex="0"/g) ?? []).length).toBe(1);
    expect(html).toContain(`data-kc-node="${VT}" data-part="kc:${VT}" data-state="explaining"`);
    const vt = html.slice(html.indexOf(`data-kc-node="${VT}"`));
    const box = vt.slice(0, vt.indexOf("</g>"));
    expect(box).toContain('tabindex="0"');
    expect(box).toContain("Explaining it back</text>");
    expect(box).toContain("Asked 3 times · 1 mistake</text>");
    expect(box).toContain("Next 1</text>");
    expect(box).toContain("may come from an earlier skill (link not yet reviewed)");
    expect(html).toContain("Maths · Not started</text>");
    expect(html).not.toContain("transition");
  });

  it("a lit gap path rings its boxes and link and dims the rest", () => {
    const html = renderToStaticMarkup(<ConceptMapSvg nodes={nodes} edges={edges} label="Physics map" t={t} active={null} gap={[GRADIENT, VT]} reducedMotion={false} onActivate={() => undefined} onFocusNode={() => undefined} />);
    expect(html).toContain(`data-gap="${GRADIENT} ${VT}"`);
    expect((html.match(/data-lit="true"/g) ?? []).length).toBe(3); // two boxes and their link
    expect(html).toContain(`data-edge="${GRADIENT}&gt;${VT}" data-kind="root_gap" data-lit="true" opacity="1"`);
    expect(html).toContain('opacity="0.3"');
    expect(html).toContain("transition:opacity");
  });

  it("arrow keys move along the column and the links", () => {
    const placed = layoutOf(nodes, edges);
    const at = new Map(placed.nodes.map((n) => [n.id, n]));
    const left = moveFrom(placed, edges, VT, "ArrowLeft")!;
    expect(edges.some((e) => e.to === VT && e.from === left)).toBe(true);
    const right = moveFrom(placed, edges, left, "ArrowRight")!;
    expect(edges.some((e) => e.from === left && e.to === right)).toBe(true);
    const down = moveFrom(placed, edges, VT, "ArrowDown");
    if (down !== null) {
      expect(at.get(down)!.layer).toBe(at.get(VT)!.layer);
      expect(at.get(down)!.y).toBeGreaterThan(at.get(VT)!.y);
      expect(moveFrom(placed, edges, down, "ArrowUp")).toBe(VT);
    }
    expect(moveFrom(placed, edges, VT, "Tab")).toBeNull();
    expect(moveFrom(placed, edges, "kc.none", "ArrowUp")).toBeNull();
  });

  it("titles wrap in two lines with an ellipsis", () => {
    expect(wrap("Find the numbers of protons, neutrons and electrons from nuclide notation", 172)).toEqual(["Find the numbers of", "protons, neutrons and…"]);
    expect(wrap("Short", 172)).toEqual(["Short"]);
  });
});
