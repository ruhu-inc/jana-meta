// The diagram drill's marking (JM-D10, SPEC §5.2): a tap is right only when it falls inside the asked part's SAM
// outline; nested parts go to the smallest; unsure or placeless parts are never asked. Every capture is synthetic.
import { describe, expect, it } from "vitest";
import type { CapturedQuestion } from "../src/capture.js";
import { area, drillOrder, drillParts, inside, markTap, partAt, type DrillPart } from "../src/diagram-drill.js";

type Region = CapturedQuestion["regions"][number];
const square = (x: number, y: number, s: number) => [{ x, y }, { x: x + s, y }, { x: x + s, y: y + s }, { x, y: y + s }];
function region(n: number, text: string, extra: Partial<Region> = {}): Region {
  return { region_id: `rgn_${n}`, kind: "diagram", order: n, text, confidence: 0.95, needs_confirmation: false, low_confidence_spans: [], language: "en", direction: "ltr", ...extra } as Region;
}
function capture(regions: Region[], purpose: CapturedQuestion["purpose"] = "diagram"): CapturedQuestion {
  return { purpose, regions } as unknown as CapturedQuestion;
}
const IMG = "img_01JZ0000000000000000000001";

const HEART = capture([
  region(0, "heart", { outline: square(0.1, 0.1, 0.8) }),
  region(1, "left ventricle", { outline: square(0.5, 0.5, 0.2), label_box: { x: 0.85, y: 0.7, w: 0.1, h: 0.04 } }),
  region(2, "aorta", { bbox: { image_id: IMG, x: 0.4, y: 0.12, w: 0.1, h: 0.1 } }),
  region(3, "[?]", { outline: square(0.2, 0.6, 0.1) }),
  region(4, "vena cava"),
  region(5, "Heart", { outline: square(0.2, 0.2, 0.1) }),
]);

describe("diagram drill", () => {
  const parts = drillParts(HEART);
  const byName = (name: string) => parts.find((p) => p.name === name) as DrillPart;

  it("asks only about named parts with a place on the photo, each name once", () => {
    expect(parts.map((p) => p.name)).toEqual(["heart", "left ventricle", "aorta"]);
    expect(byName("aorta").outline).toHaveLength(4); // no outline: its box
    expect(byName("left ventricle").label).toEqual({ x: 0.85, y: 0.7, w: 0.1, h: 0.04 });
    expect(drillParts(capture(HEART.regions, "sketch"))).toEqual([]);
  });

  it("marks a tap inside the asked outline right and gives a nested tap to the smallest part", () => {
    expect(markTap(parts, byName("left ventricle"), { x: 0.6, y: 0.6 })).toMatchObject({ outcome: "correct" });
    expect(markTap(parts, byName("heart"), { x: 0.6, y: 0.6 })).toMatchObject({ outcome: "other_part", part: { name: "left ventricle" } });
    expect(markTap(parts, byName("heart"), { x: 0.3, y: 0.8 })).toMatchObject({ outcome: "correct" });
  });

  it("allows a finger's width at an edge and nothing more", () => {
    const solo = [byName("left ventricle")];
    expect(partAt(solo, { x: 0.71, y: 0.6 })?.name).toBe("left ventricle");
    expect(partAt(solo, { x: 0.75, y: 0.6 })).toBeNull();
    expect(markTap(solo, solo[0]!, { x: 0.05, y: 0.05 })).toEqual({ outcome: "missed" });
  });

  it("uses the even-odd rule and the shoelace area", () => {
    const l = [{ x: 0, y: 0 }, { x: 1, y: 0 }, { x: 1, y: 0.2 }, { x: 0.2, y: 0.2 }, { x: 0.2, y: 1 }, { x: 0, y: 1 }];
    expect(inside({ x: 0.1, y: 0.5 }, l)).toBe(true);
    expect(inside({ x: 0.5, y: 0.5 }, l)).toBe(false);
    expect(area(square(0, 0, 0.5))).toBeCloseTo(0.25);
  });

  it("shuffles the same way for the same seed and keeps every part", () => {
    expect(drillOrder(parts, 7).map((p) => p.name)).toEqual(drillOrder(parts, 7).map((p) => p.name));
    expect([...drillOrder(parts, 7)].map((p) => p.name).sort()).toEqual(parts.map((p) => p.name).sort());
  });
});
