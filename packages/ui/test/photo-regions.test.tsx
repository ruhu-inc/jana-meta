// JM-D10 (SPEC §5): the place Jana points at, outlined on the student's own photo. A `board.highlight` naming
// `photo_regions` (the first wrong line of photographed working, or the wrong part of a photographed sketch) shows the
// photo with SAM 3.1's outline of that place lit and the others faint; the place is also said in words.
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";
import { SessionController, parseTarget, typedCapture, type CapturedQuestion } from "@jana/client-core";
import { Board } from "../src/board/Board.js";
import { PhotoRegions, regionPoints } from "../src/board/PhotoRegions.js";
import { PhotoCapture } from "../src/composer/PhotoCapture.js";
import { LocaleProvider } from "../src/i18n.js";
import { StoreProvider } from "../src/store.js";
import { Fixture, SESSION } from "./harness.js";

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

const CAP = `cap_${"1".repeat(26)}`;
const IMG = `img_${"2".repeat(26)}`;
const BOARD = `brd_${"3".repeat(26)}`;
const STEP = `stp_${"4".repeat(26)}`;

function line(n: number, text: string, top: number, outline = true): CapturedQuestion["regions"][number] {
  const box = { image_id: IMG, x: 0.1, y: top, w: 0.6, h: 0.1 };
  return {
    region_id: `rgn_${n}`, kind: "working_line", order: n, text, confidence: 0.95, needs_confirmation: false,
    low_confidence_spans: [], language: "en", direction: "ltr", bbox: box,
    ...(outline ? { outline: [{ x: 0.1, y: top }, { x: 0.7, y: top }, { x: 0.7, y: top + 0.1 }, { x: 0.1, y: top + 0.1 }] } : {}),
  } as CapturedQuestion["regions"][number];
}

function workingCapture(): CapturedQuestion {
  const base = typedCapture("3x + 5 = 20\n3x = 20 + 5\nx = 25/3", { sessionId: SESSION, purpose: "working", confirmed: true });
  return {
    ...base, capture_id: CAP, source: "photo_file",
    attachments: [{ image_id: IMG, kind: "photo", width: 800, height: 600, bytes: 20, sha256: "a".repeat(64) }],
    regions: [line(0, "3x + 5 = 20", 0.1), line(1, "3x = 20 + 5", 0.3), line(2, "x = 25/3", 0.5, false)],
  } as CapturedQuestion;
}

function session(reads: string[], capture = workingCapture()): SessionController {
  return new SessionController({ endpoint: async () => ({ baseUrl: "http://core.test", token: "synthetic" }) }, new Fixture().holder, SESSION, {
    fetch: async (url) => {
      reads.push(String(url));
      if (String(url).endsWith(`/v1/captures/${CAP}`)) return new Response(JSON.stringify(capture), { headers: { "content-type": "application/json" } });
      return new Response(new Blob(["synthetic screened photo"], { type: "image/jpeg" }));
    },
  });
}

describe("JM-D10 photo regions", () => {
  test("photo_region_outline_lights_the_wrong_line_on_the_students_photo", async () => {
    const reads: string[] = [];
    const controller = session(reads);
    vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:working-photo");
    const revoke = vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => undefined);
    const view = render(<LocaleProvider locale="en"><StoreProvider holder={new Fixture().holder} session={controller}>
      <PhotoRegions sessionId={SESSION} captureId={CAP} lit={[`${CAP}:rgn_1`]} />
    </StoreProvider></LocaleProvider>);
    try {
      await waitFor(() => expect(screen.getByRole("img", { name: "Your photo" }).getAttribute("src")).toBe("blob:working-photo"));
      expect(reads).toEqual([`http://core.test/v1/captures/${CAP}`, `http://core.test/v1/captures/${CAP}/images/${IMG}`]);
      const outlines = [...view.container.querySelectorAll("polygon[data-photo-region]")];
      expect(outlines.map((p) => p.getAttribute("data-photo-region"))).toEqual([`${CAP}:rgn_0`, `${CAP}:rgn_1`, `${CAP}:rgn_2`]);
      const lit = outlines.filter((p) => p.hasAttribute("data-lit"));
      expect(lit.map((p) => p.getAttribute("data-photo-region"))).toEqual([`${CAP}:rgn_1`]);
      expect(lit[0]?.getAttribute("points")).toBe("0.1,0.3 0.7,0.3 0.7,0.4 0.1,0.4");
      // Never colour alone: the place is said in words too.
      expect(view.container.querySelector("figcaption")?.textContent).toBe("Showing on your photo: 3x = 20 + 5");
      view.unmount();
      expect(revoke).toHaveBeenCalledWith("blob:working-photo");
    } finally { controller.close(); }
  });

  test("photo_region_caption_renders_a_maths_line_instead_of_its_raw_delimiters", async () => {
    const capture = workingCapture();
    capture.regions[1] = line(1, "\\(3x = 27\\)", 0.3);
    const controller = session([], capture);
    vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:working-photo");
    vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => undefined);
    const view = render(<LocaleProvider locale="en"><StoreProvider holder={new Fixture().holder} session={controller}>
      <PhotoRegions sessionId={SESSION} captureId={CAP} lit={[`${CAP}:rgn_1`]} />
    </StoreProvider></LocaleProvider>);
    try {
      await waitFor(() => expect(view.container.querySelector("figcaption")?.textContent).toMatch(/^Showing on your photo: /));
      const caption = view.container.querySelector("figcaption")!;
      expect(caption.textContent).not.toContain("\\(");
      expect(caption.querySelector(".katex")).not.toBeNull();
    } finally { controller.close(); }
  });

  test("photo_region_without_an_outline_falls_back_to_its_box_and_nothing_without_either", () => {
    const [outlined, , boxed] = workingCapture().regions;
    expect(regionPoints(outlined!)).toBe("0.1,0.1 0.7,0.1 0.7,0.2 0.1,0.2");
    expect(regionPoints(boxed!)).toBe("0.1,0.5 0.7,0.5 0.7,0.6 0.1,0.6");
    expect(regionPoints({ ...boxed!, bbox: null })).toBeNull();
  });

  test("photo_region_board_highlight_shows_the_photo_beside_the_lit_line", async () => {
    const reads: string[] = [];
    const controller = session(reads);
    vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:working-photo");
    vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => undefined);
    const f = new Fixture();
    f.startTurn();
    f.emit({ type: "board.step", board_id: BOARD, step_id: STEP, index: 0, latex: "3x = 20 + 5", reason: null, owner: "student", status: "incorrect", check_id: null, error: null }, null);
    const view = render(<LocaleProvider locale="en"><StoreProvider holder={f.holder} session={controller}><Board sessionId={SESSION} /></StoreProvider></LocaleProvider>);
    try {
      expect(view.container.querySelector("[data-photo-capture]")).toBeNull(); // no photo until a place on it is lit
      f.emit({ type: "board.highlight", board_id: BOARD, step_ids: [STEP], ttl_ms: null, photo_regions: [`${CAP}:rgn_1`] }, null);
      await waitFor(() => expect(view.container.querySelector(`polygon[data-photo-region="${CAP}:rgn_1"][data-lit]`)).not.toBeNull());
      expect(f.holder.getState().boards[BOARD]?.highlight?.photo_regions).toEqual([`${CAP}:rgn_1`]);
    } finally { view.unmount(); controller.close(); }
  });

  test("photo_region_cue_targets_parse_exactly", () => {
    expect(parseTarget(`${CAP}:rgn_1`)).toEqual({ kind: "photo_region", capture_id: CAP, region_id: "rgn_1" });
    for (const bad of [`${CAP}:rgn_`, `${CAP}:region_1`, "cap_1:rgn_1", `${CAP}:rgn_1234`]) expect(parseTarget(bad)).toBeNull();
  });
});

describe("JM-D10 photo capture of working and sketches", () => {
  const confirmable = (purpose: "working" | "sketch"): CapturedQuestion => ({ ...workingCapture(), purpose, status: "awaiting_confirmation",
    confirmation: { confirmed: false, method: "pending", edit_distance: 0, confirmed_at: null } } as CapturedQuestion);

  test("photo_region_outlines_show_while_the_student_confirms_a_sketch", () => {
    const view = render(<LocaleProvider locale="en"><StoreProvider holder={new Fixture().holder} session={null}>
      <PhotoCapture sessionId={SESSION} purpose="sketch" previewCapture={confirmable("sketch")} previewImage="data:image/jpeg;base64,AA==" onConfirmed={() => undefined} onTyped={() => undefined} onClose={() => undefined} />
    </StoreProvider></LocaleProvider>);
    expect(view.container.textContent).toContain("Is this what you drew?");
    const outlines = [...view.container.querySelectorAll("polygon[data-photo-region]")].map((p) => p.getAttribute("data-photo-region"));
    expect(outlines).toEqual([`${CAP}:rgn_0`, `${CAP}:rgn_1`]); // the third line has only a box, drawn as before
  });

  test("photo_region_working_photos_offer_the_online_reader_after_its_notice", () => {
    const drafting = { ...confirmable("working"), status: "drafting" } as CapturedQuestion;
    render(<LocaleProvider locale="en"><StoreProvider holder={new Fixture().holder} session={null}>
      <PhotoCapture sessionId={SESSION} purpose="working" previewCapture={drafting} onConfirmed={() => undefined} onTyped={() => undefined} onClose={() => undefined} />
    </StoreProvider></LocaleProvider>);
    expect(screen.getByRole("checkbox", { name: /Send this photo to the online tutor/ })).toHaveProperty("checked", false);
  });
});
