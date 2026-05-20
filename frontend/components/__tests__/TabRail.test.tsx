/**
 * These tests make sure the left rail only opens hover preview for the
 * tabs that should support it right now.
 *
 * Each test checks one simple hover behavior.
 */

import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { TabRail } from "../TabRail";
import { useSimulationStore } from "../../store";

vi.useFakeTimers();

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) =>
      (
        {
          "simPage.tabs.workspace": "Workspace",
          "simPage.tabs.agents": "Agents",
          "simPage.tabs.intervention": "Intervention",
          "simPage.tabs.analyse": "Analyse",
        } as Record<string, string>
      )[key] ?? key,
  }),
}));

describe("TabRail", () => {
  beforeEach(() => {
    useSimulationStore.setState({
      activeTab: "workspace",
      peekTab: null,
      peekOverlayActive: false,
    } as never);
  });

  it("opens hover preview for the agents tab", () => {
    render(<TabRail width={96} />);

    expect(screen.getByText("Workspace")).toBeInTheDocument();
    expect(screen.getByText("Agents")).toBeInTheDocument();
    fireEvent.mouseEnter(screen.getByTitle("Agents"));
    vi.advanceTimersByTime(350);

    expect(useSimulationStore.getState().peekTab).toBe("agents");
  });

  it("does not open hover preview for the intervention tab", () => {
    render(<TabRail width={96} />);

    fireEvent.mouseEnter(screen.getByTitle("Intervention"));
    vi.advanceTimersByTime(350);

    expect(useSimulationStore.getState().peekTab).toBeNull();
  });
});
