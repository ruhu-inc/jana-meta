// The concept map's layout (UXS-22 map view) on the real Physics and Maths O level backbones, as the core serves them
// (fixtures written by services/agent-core/tests/test_concept_map.py): deterministic whatever the input order, every
// skill right of each skill it builds on, no two boxes overlapping, edges routed between columns, and the crossing
// reduction doing better than the syllabus order it starts from.
import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { layout, overlaps, NODE_HEIGHT, type LayoutEdge, type LayoutNode } from "../src/conceptmap/layout.js";
import { FIXTURES } from "./helpers.js";

interface Backbone { nodes: { id: string; code: string; linked: boolean }[]; edges: { from: string; to: string; kind: string }[] }

function backbone(subject: string): { nodes: LayoutNode[]; edges: LayoutEdge[] } {
  const raw = JSON.parse(fs.readFileSync(path.join(FIXTURES, "concept-map", `${subject}.json`), "utf8")) as Backbone;
  return { nodes: raw.nodes.map((n) => ({ id: n.id, order: n.code, late: n.linked })), edges: raw.edges.map((e) => ({ from: e.from, to: e.to })) };
}

function shuffled<T>(items: readonly T[], seed: number): T[] {
  const out = [...items];
  let s = seed;
  for (let i = out.length - 1; i > 0; i--) {
    s = (s * 1103515245 + 12345) % 2147483648;
    const j = s % (i + 1);
    [out[i], out[j]] = [out[j]!, out[i]!];
  }
  return out;
}

describe("concept map layout", () => {
  for (const subject of ["phy", "mth"]) {
    it(`${subject}: deterministic, layered, no overlaps`, () => {
      const { nodes, edges } = backbone(subject);
      expect(nodes.length).toBeGreaterThan(100);
      const first = layout(nodes, edges);
      expect(layout(shuffled(nodes, 7), shuffled(edges, 11))).toEqual(first);
      expect(layout(nodes, edges)).toEqual(first);
      expect(first.nodes).toHaveLength(nodes.length);
      const at = new Map(first.nodes.map((n) => [n.id, n]));
      for (const e of edges) expect(at.get(e.from)!.layer).toBeLessThan(at.get(e.to)!.layer);
      for (let i = 0; i < first.nodes.length; i++) {
        for (let j = i + 1; j < first.nodes.length; j++) {
          expect(overlaps(first.nodes[i]!, first.nodes[j]!), `${first.nodes[i]!.id} / ${first.nodes[j]!.id}`).toBe(false);
        }
      }
      for (const n of first.nodes) {
        expect(n.x).toBeGreaterThanOrEqual(0);
        expect(n.y).toBeGreaterThanOrEqual(0);
        expect(n.x + n.width).toBeLessThanOrEqual(first.width);
        expect(n.y + n.height).toBeLessThanOrEqual(first.height);
      }
      // Each edge leaves its source's right side, enters its target's left side, and its route moves rightwards.
      for (const e of first.edges) {
        const xs = e.points.map((p) => p.x);
        expect(xs).toEqual([...xs].sort((a, b) => a - b));
        expect(e.points[0]).toEqual({ x: at.get(e.from)!.x + at.get(e.from)!.width, y: at.get(e.from)!.y + NODE_HEIGHT / 2 });
        // A dummy point never sits inside a box of its column.
        for (const p of e.points.slice(1, -1)) {
          for (const n of first.nodes) expect(p.x > n.x && p.x < n.x + n.width && p.y > n.y && p.y < n.y + n.height).toBe(false);
        }
      }
      // Crossing reduction does clearly better than the syllabus order it starts from.
      const naive = layout(nodes, edges, { sweeps: 0 });
      expect(first.crossings).toBeLessThan(naive.crossings * 0.75);
      expect(first.layers).toBeGreaterThanOrEqual(8);
      // A linked skill of another subject that the map's skills build on sits just left of the first skill its root gap reaches.
      for (const n of nodes.filter((x) => x.late === true && !edges.some((e) => e.to === x.id))) {
        const reach = edges.filter((e) => e.from === n.id).map((e) => at.get(e.to)!.layer);
        expect(at.get(n.id)!.layer).toBe(Math.max(0, Math.min(...reach) - 1));
      }
    });
  }

  it("breaks a cycle at the closing edge and keeps going", () => {
    const placed = layout([{ id: "a", order: "1" }, { id: "b", order: "2" }, { id: "c", order: "3" }], [{ from: "a", to: "b" }, { from: "b", to: "c" }, { from: "c", to: "a" }]);
    expect(placed.nodes.map((n) => [n.id, n.layer])).toEqual([["a", 0], ["b", 1], ["c", 2]]);
    expect(placed.edges).toHaveLength(3);
  });

  it("an empty map has no size", () => {
    expect(layout([], [])).toEqual({ nodes: [], edges: [], width: 0, height: 0, layers: 0, crossings: 0 });
  });
});
