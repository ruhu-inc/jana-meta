// A root-gap card says what it is about (`card.open` `about`): under the card in the conversation, "See it on the map"
// opens the concept map of the KC's subject with the gap path lit (the app's GapLinkProvider). A card with no `about`,
// or a screen with no provider, shows no link.
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, expect, test, vi } from "vitest";
import type { SessionController } from "@jana/client-core";
import { LocaleProvider } from "../src/i18n.js";
import { GapLinkProvider, type GapOnMap } from "../src/learn/link.js";
import { RegistryProvider } from "../src/registry/registry.js";
import { StoreProvider } from "../src/store.js";
import { TutorScreen } from "../src/TutorScreen.js";
import { defaultRegistry } from "../src/transcript/parts.js";
import { Fixture, SESSION, id } from "./harness.js";

afterEach(() => cleanup());

const ABOUT = { kind: "root_gap", kc_id: "kc.phy.o.motion.velocity_time_gradient", root_kc_id: "kc.mth.o.coordinate_geometry.gradient", misconception_id: "mc.phy.o.vt_gradient_from_one_point" } as const;

function double(): SessionController {
  return {
    sessionId: SESSION, answerCard: vi.fn(async () => "accepted"), setMode: vi.fn(async () => undefined),
    commands: { post: vi.fn(async () => undefined), get: vi.fn(async () => ({ captures: [] })), put: vi.fn(async () => undefined), patch: vi.fn(async () => undefined), delete: vi.fn(async () => undefined) },
    send: vi.fn(), sendCapture: vi.fn(), cancel: vi.fn(), discardFailed: vi.fn(), retryTurn: vi.fn(async () => undefined),
  } as unknown as SessionController;
}

function card(f: Fixture, about: boolean): void {
  f.startTurn();
  const part = id("prt");
  f.emit({ type: "part.start", part_id: part, kind: "card", index: 0 });
  f.emit({ type: "card.open", request_id: id("req"), part_id: part, call_id: null, ...(about ? { about: ABOUT } : {}),
    card: { card_type: "question", prompt: "This is really about the gradient of a straight line.", options: [{ id: "opt_1", label: "Practise the gradient of a straight line first", recommended: true }, { id: "opt_2", label: "Not now, I'll keep trying", recommended: false }], allow_free_text: false, multi: false } });
  f.emit({ type: "part.end", part_id: part, status: "complete", duration_ms: 1 });
  f.end();
}

function show(f: Fixture, open: ((gap: GapOnMap) => void) | null): void {
  const screenNode: ReactNode = <StoreProvider holder={f.holder} session={double()}><TutorScreen sessionId={SESSION} /></StoreProvider>;
  render(
    <LocaleProvider locale="en"><RegistryProvider registry={defaultRegistry()}>
      {open === null ? screenNode : <GapLinkProvider open={open}>{screenNode}</GapLinkProvider>}
    </RegistryProvider></LocaleProvider>,
  );
}

test("a_root_gap_card_links_to_its_gap_on_the_map", () => {
  const f = new Fixture();
  card(f, true);
  const open = vi.fn();
  show(f, open);
  fireEvent.click(screen.getByRole("button", { name: "See it on the map" }));
  expect(open).toHaveBeenCalledWith({ kc_id: ABOUT.kc_id, root_kc_id: ABOUT.root_kc_id, misconception_id: ABOUT.misconception_id });
});

test("no_link_without_about_or_without_a_provider", () => {
  const f = new Fixture();
  card(f, false);
  show(f, vi.fn());
  expect(screen.queryByRole("button", { name: "See it on the map" })).toBeNull();
  cleanup();
  const g = new Fixture();
  card(g, true);
  show(g, null);
  expect(screen.queryByRole("button", { name: "See it on the map" })).toBeNull();
});
