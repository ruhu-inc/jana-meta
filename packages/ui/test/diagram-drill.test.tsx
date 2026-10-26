// JM-D10 (SPEC §5.2): the diagram drill on the student's own photo of a labelled diagram. "Learn the parts" names a
// tapped part; "Practise" hides the printed labels, asks "Tap the …" and marks each tap by its place inside the part's
// outline; two misses show the part; the drill ends with how many were found first time. Every capture is synthetic.
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";
import { SessionController, typedCapture, type CapturedQuestion } from "@jana/client-core";
import { DiagramDrill } from "../src/composer/DiagramDrill.js";
import { LocaleProvider } from "../src/i18n.js";
import { StoreProvider } from "../src/store.js";
import { Fixture, SESSION } from "./harness.js";

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

const CAP = `cap_${"5".repeat(26)}`;
const IMG = `img_${"6".repeat(26)}`;
type Region = CapturedQuestion["regions"][number];
const square = (x: number, y: number, s: number) => [{ x, y }, { x: x + s, y }, { x: x + s, y: y + s }, { x, y: y + s }];

function part(n: number, text: string, x: number, y: number, outline = true): Region {
  return { region_id: `rgn_${n}`, kind: "diagram", order: n, text, confidence: 0.95, needs_confirmation: false, low_confidence_spans: [],
    language: "en", direction: "ltr", bbox: { image_id: IMG, x, y, w: 0.2, h: 0.2 }, label_box: { x: 0.8, y: y, w: 0.15, h: 0.05 },
    ...(outline ? { outline: square(x, y, 0.2) } : {}) } as Region;
}

function diagram(outlined = true): CapturedQuestion {
  const base = typedCapture("left ventricle\nright atrium", { sessionId: SESSION, purpose: "diagram", confirmed: true });
  return { ...base, capture_id: CAP, source: "photo_file", status: "confirmed",
    attachments: [{ image_id: IMG, kind: "photo", width: 800, height: 800, bytes: 20, sha256: "a".repeat(64) }],
    regions: [part(0, "left ventricle", 0.1, 0.1), part(1, "right atrium", 0.5, 0.5, outlined)] } as CapturedQuestion;
}

function session(reads: string[], later: CapturedQuestion): SessionController {
  return new SessionController({ endpoint: async () => ({ baseUrl: "http://core.test", token: "synthetic" }) }, new Fixture().holder, SESSION, {
    fetch: async (url) => {
      reads.push(String(url));
      if (String(url).endsWith(`/v1/captures/${CAP}`)) return new Response(JSON.stringify(later), { headers: { "content-type": "application/json" } });
      return new Response(new Blob(["synthetic screened photo"], { type: "image/jpeg" }));
    },
  });
}

async function open(capture: CapturedQuestion, later = capture) {
  const reads: string[] = [];
  const controller = session(reads, later);
  vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:diagram");
  vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => undefined);
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue({ left: 0, top: 0, width: 100, height: 100, right: 100, bottom: 100, x: 0, y: 0, toJSON: () => ({}) } as DOMRect);
  const view = render(<LocaleProvider locale="en"><StoreProvider holder={new Fixture().holder} session={controller}>
    <DiagramDrill sessionId={SESSION} capture={capture} onClose={() => undefined} />
  </StoreProvider></LocaleProvider>);
  await waitFor(() => expect(screen.getByRole("img", { name: "Your diagram" }).getAttribute("src")).toBe("blob:diagram"));
  const picture = screen.getByRole("img", { name: "Your diagram" }).parentElement!;
  const tapAt = (x: number, y: number) => fireEvent.click(picture, { clientX: x * 100, clientY: y * 100 });
  return { view, controller, reads, tapAt };
}

describe("JM-D10 diagram drill", () => {
  test("diagram_learn_mode_names_the_tapped_part", async () => {
    const { view, controller, tapAt } = await open(diagram());
    try {
      expect(view.container.querySelectorAll("rect[data-diagram-label]")).toHaveLength(0); // labels show while learning
      tapAt(0.2, 0.2);
      expect(view.container.textContent).toContain("This is the left ventricle.");
      expect(view.container.querySelector("polygon[data-lit]")?.getAttribute("data-diagram-part")).toBe("rgn_0");
    } finally { view.unmount(); controller.close(); }
  });

  test("diagram_practice_hides_labels_and_marks_taps_against_the_outline", async () => {
    vi.spyOn(Date, "now").mockReturnValue(7);
    const { view, controller, tapAt } = await open(diagram());
    try {
      fireEvent.click(screen.getByRole("button", { name: "Practise" }));
      expect(view.container.querySelectorAll("rect[data-diagram-label]")).toHaveLength(2);
      expect(view.container.textContent).toContain("The labels are hidden.");
      const first = view.container.querySelector("[data-diagram-ask]")!.getAttribute("data-diagram-ask");
      const [right, wrong] = first === "rgn_0" ? [[0.2, 0.2], [0.6, 0.6]] : [[0.6, 0.6], [0.2, 0.2]];
      tapAt(wrong[0]!, wrong[1]!);
      expect(view.container.textContent).toMatch(/That's the (left ventricle|right atrium)\. Try again\./);
      tapAt(right[0]!, right[1]!);
      expect(view.container.textContent).toMatch(/Yes, that's the /);
      fireEvent.click(screen.getByRole("button", { name: "Next" }));
      tapAt(0.95, 0.05); // on no part
      expect(view.container.textContent).toContain("That isn't one of the parts. Try again.");
      tapAt(0.95, 0.05);
      expect(view.container.textContent).toMatch(/Here is the /); // two misses: the part is shown
      expect(view.container.querySelector("polygon[data-lit]")?.getAttribute("data-diagram-part")).not.toBe(first);
      fireEvent.click(screen.getByRole("button", { name: "Next" }));
      expect(screen.getByRole("status").textContent).toBe("You found 0 of 2 first time.");
      fireEvent.click(screen.getByRole("button", { name: "Practise again" }));
      expect(view.container.textContent).toContain("Part 1 of 2");
    } finally { view.unmount(); controller.close(); }
  });

  test("diagram_outlines_arriving_after_confirmation_replace_the_boxes", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      const { view, controller, reads } = await open(diagram(false), diagram(true));
      try {
        expect(view.container.querySelector('polygon[data-diagram-part="rgn_1"]')?.getAttribute("points")).toBe("0.5,0.5 0.7,0.5 0.7,0.7 0.5,0.7");
        await vi.advanceTimersByTimeAsync(1600);
        await waitFor(() => expect(reads.filter((u) => u.endsWith(`/v1/captures/${CAP}`))).toHaveLength(1));
        await vi.advanceTimersByTimeAsync(5000);
        expect(reads.filter((u) => u.endsWith(`/v1/captures/${CAP}`))).toHaveLength(1); // every part outlined: no more fetches
      } finally { view.unmount(); controller.close(); }
    } finally { vi.useRealTimers(); }
  });

  test("diagram_with_too_few_named_parts_says_so", async () => {
    const one = { ...diagram(), regions: [part(0, "left ventricle", 0.1, 0.1), { ...part(1, "[?]", 0.5, 0.5) }] } as CapturedQuestion;
    const reads: string[] = [];
    const controller = session(reads, one);
    const view = render(<LocaleProvider locale="en"><StoreProvider holder={new Fixture().holder} session={controller}>
      <DiagramDrill sessionId={SESSION} capture={one} onClose={() => undefined} />
    </StoreProvider></LocaleProvider>);
    try {
      expect(view.container.textContent).toContain("I couldn't find enough named parts");
      expect(screen.queryByRole("button", { name: "Practise" })).toBeNull();
    } finally { view.unmount(); controller.close(); }
  });
});
