// SPEC §19.5.2 (W8 phase 1) on screen: the Last time card shows the sentence the core made from its facts, as text,
// adds no number of its own, offers Study, and is simply absent when the core gives no card (loading, an older core,
// a failed read). On Home its sentence leads the Continue learning block; in Study's library it is a card.
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";
import type { CompanionView, Opener } from "@jana/client-core";
import { Home } from "../src/home/Home.js";
import { LastTimeCard } from "../src/home/LastTimeCard.js";
import { LocaleProvider } from "../src/i18n.js";

afterEach(() => cleanup());

const OPENER: Opener = {
  opener_id: "2026-11-04",
  text: "Last time you worked on physics in Study today; 8 cards are due and your exam is in 19 days.",
  facts: {
    last_session_date: "2026-11-04", last_session_mode: "study", last_subject: "physics", next_step: null, learner_cards_due: 8,
    study_cards_due: 0, exam_distance_days: 19, pack_ready: false, checkin_id: null,
  },
};
const READY: CompanionView = { status: "ready", opener: OPENER };

const shown = (node: React.ReactElement) => render(<LocaleProvider locale="en">{node}</LocaleProvider>);

describe("W8 Last time card", () => {
  test("the card shows the core's sentence as text and every number in it is a fact", () => {
    const onOpenStudy = vi.fn();
    const { container } = shown(<LastTimeCard view={READY} onOpenStudy={onOpenStudy} />);
    const card = container.querySelector("[data-last-time]") as HTMLElement;
    expect(card.getAttribute("data-last-time")).toBe("2026-11-04");
    expect(card.querySelector("[data-last-time-text]")?.textContent).toBe(OPENER.text);
    expect(screen.getByRole("heading", { name: "Last time" })).toBeDefined();
    const numbers = (card.textContent ?? "").match(/\d+/g) ?? [];
    expect(numbers.map(Number).sort((a, b) => a - b)).toEqual([8, 19]);
    fireEvent.click(screen.getByRole("button", { name: "Open Study" }));
    expect(onOpenStudy).toHaveBeenCalledOnce();
  });

  test("markup in the text stays text", () => {
    const { container } = shown(<LastTimeCard view={{ status: "ready", opener: { ...OPENER, text: "<b>bold</b> physics" } }} />);
    expect(container.querySelector("b")).toBeNull();
    expect(container.textContent).toContain("<b>bold</b> physics");
    expect(screen.queryByRole("button")).toBeNull(); // no Study offer where Study is not available
  });

  test("no card while loading, on an older core or after a failed read", () => {
    for (const view of [
      { status: "idle", opener: null }, { status: "loading", opener: null }, { status: "unavailable", opener: null }, { status: "failed", opener: null },
    ] as CompanionView[]) {
      const { container } = shown(<LastTimeCard view={view} />);
      expect(container.querySelector("[data-last-time]")).toBeNull();
      cleanup();
    }
  });

  test("on Home the sentence leads the Continue learning block verbatim, without a heading of its own, above the plan and the countdown", () => {
    const onOpenStudy = vi.fn();
    shown(
      <Home name="Ada" ask={null} subjects={[]} onSubject={() => undefined} pickup={[]} onPickup={() => undefined}
        practice={{ ideas: [], refreshes: 0, subjectLabel: (s) => s }} onPractice={() => undefined}
        countdown={<section data-exam-countdown="19" />} lastTime={<LastTimeCard view={READY} onOpenStudy={onOpenStudy} />} plan={<p data-plan="">Next up</p>} />,
    );
    const block = screen.getByRole("region", { name: "Continue learning" });
    const card = block.querySelector("[data-last-time]") as HTMLElement;
    expect(card.getAttribute("data-last-time")).toBe("2026-11-04");
    expect(card.querySelector("[data-last-time-text]")?.textContent).toBe(OPENER.text);
    expect(within(block).queryByRole("heading", { name: "Last time" })).toBeNull();
    const plan = block.querySelector("[data-plan]") as HTMLElement;
    const countdown = block.querySelector("[data-exam-countdown]") as HTMLElement;
    expect(card.compareDocumentPosition(plan) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(plan.compareDocumentPosition(countdown) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    fireEvent.click(within(block).getByRole("button", { name: "Open Study" }));
    expect(onOpenStudy).toHaveBeenCalledOnce();
  });

  test("Home has no Continue learning block while the core gives nothing to continue", () => {
    shown(
      <Home name="Ada" ask={null} subjects={[]} onSubject={() => undefined} pickup={[]} onPickup={() => undefined}
        practice={{ ideas: [], refreshes: 0, subjectLabel: (s) => s }} onPractice={() => undefined}
        lastTime={<LastTimeCard view={{ status: "loading", opener: null }} />} plan={<div className="flex flex-col gap-4" />} />,
    );
    expect(screen.queryByRole("region", { name: "Continue learning" })).toBeNull();
    expect(document.querySelector("[data-home-continue]")?.hasAttribute("hidden")).toBe(true);
  });
});
