// The learner's map scrubber (SPEC §21.5, §21.8; W10): a labelled range over weekly dates from the profile's first
// learning event (at most 26 weeks) to today, the date read aloud and shown in words; a date replays the map on the
// core (`?as_of=`) and redraws it read-only with "as of <date>" in the table; "Today" returns to the live map without
// a read; a date the core refuses keeps the map shown and says so. Through the real controller against the fake core.
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useSyncExternalStore } from "react";
import { afterEach, describe, expect, test } from "vitest";
import { ConceptMapController, ProfileController, StoreHolder, readConceptMap, type ConceptMap } from "@jana/client-core";
import { FakeProfileCore, PROFILES } from "../../client-core/test/profilecore.js";
import { LocaleProvider } from "../src/i18n.js";
import { ConceptMapContent, ConceptMapRendererProvider, type ConceptMapRenderer } from "../src/learn/ConceptMap.js";
import { layered } from "./learner-map-fixtures.js";

const SUBJECT = "cur.phy.o";
const VT = "kc.phy.o.motion.velocity_time_gradient";
const Drawing: ConceptMapRenderer = ({ nodes, label }) => <div role="group" aria-label={label}>{nodes.map((n) => <span key={n.id} data-kc-node={n.id}>{n.stateWord}</span>)}</div>;

afterEach(() => cleanup());

function Harness({ controller }: { controller: ConceptMapController }) {
  const view = useSyncExternalStore(controller.subscribe, controller.getView);
  const lens = useSyncExternalStore(controller.subscribe, controller.getLens);
  return (
    <LocaleProvider locale="en"><ConceptMapRendererProvider value={Drawing}>
      <ConceptMapContent view={view} lens={{ lens, onLayer: (l) => controller.setLayer(l), onScrub: (d) => void controller.scrub(d), onLinks: (k) => void controller.links(k), today: "2026-10-31" }} />
    </ConceptMapRendererProvider></LocaleProvider>
  );
}

async function opened() {
  const core = new FakeProfileCore();
  const profiles = new ProfileController(core.launch, new StoreHolder(), { fetch: core.fetch });
  await profiles.load();
  expect(await profiles.unlock(PROFILES[1]!.profile_id)).toBe(true);
  const live = { ...layered(), first_day: "2026-09-20" } as ConceptMap;
  core.conceptMaps.set(SUBJECT, live);
  const before = readConceptMap({ ...live, as_of: "2026-10-03", nodes: live.nodes.map((n) => ({ ...n, state: "not_started", band: "not_started", freshness: "never", changed_since: null })) });
  core.datedMaps.set(`${SUBJECT}@2026-10-03`, before);
  const controller = new ConceptMapController(profiles);
  await controller.load(SUBJECT);
  render(<Harness controller={controller} />);
  return { core, controller };
}

describe("learner's map scrubber", () => {
  test("weekly_dates_from_the_first_event_labelled_and_read_aloud", async () => {
    await opened();
    const range = screen.getByRole("slider", { name: "See the map as it was" }) as HTMLInputElement;
    // 20 September is in the week before 26 September: today and six weeks back.
    expect(range.max).toBe("6");
    expect(range.value).toBe("6");
    expect(range.getAttribute("aria-valuetext")).toBe("Today");
    fireEvent.change(range, { target: { value: "2" } });
    await waitFor(() => expect(range.getAttribute("aria-valuetext")).toBe("As of 3 October 2026, 4 weeks ago"));
    expect(document.querySelector("[data-scrubber-date]")!.textContent).toBe("As of 3 October 2026, 4 weeks ago");
  });

  test("a_date_replays_the_map_read_only_and_today_restores_it_without_a_read", async () => {
    const { core, controller } = await opened();
    fireEvent.change(screen.getByRole("slider"), { target: { value: "2" } });
    await waitFor(() => expect(controller.getView().map?.as_of).toBe("2026-10-03"));
    expect(document.querySelector(`[data-kc-node="${VT}"]`)!.textContent).toBe("Not started");
    expect(document.querySelector("[data-as-of]")!.textContent).toBe("As of 3 October 2026. Nothing here changes your progress.");
    fireEvent.click(screen.getByRole("radio", { name: "Table" }));
    expect(document.querySelector("caption")!.textContent).toContain("As of 3 October 2026");
    const reads = () => core.log.filter((l) => l.path === `/v1/curriculum/${SUBJECT}/concept-map`).length;
    const before = reads();
    fireEvent.click(screen.getByRole("button", { name: "Today" }));
    await waitFor(() => expect(controller.getView().map?.as_of ?? null).toBeNull());
    expect(reads()).toBe(before);
    expect(screen.getByRole("slider").getAttribute("aria-valuetext")).toBe("Today");
  });

  test("a_refused_date_keeps_the_map_and_says_so", async () => {
    const { controller } = await opened();
    fireEvent.change(screen.getByRole("slider"), { target: { value: "0" } });
    await waitFor(() => expect(screen.getByText("That date couldn't be shown. Today's map is still here.")).toBeTruthy());
    expect(controller.getView().map?.as_of ?? null).toBeNull();
  });
});
