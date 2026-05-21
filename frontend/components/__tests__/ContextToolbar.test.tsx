/**
 * These tests make sure the workspace toolbar keeps a compact overflow
 * menu for lower-priority actions.
 *
 * Each test checks one visible menu behavior.
 */

import React from "react";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ContextToolbar from "../ContextToolbar";
import { useSimulationStore } from "../../store";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) =>
      (
        {
          "simPage.advance": "Advance node",
          "simPage.branch": "Create branch",
          "simPage.autoAdvance": "Auto advance",
          "simPage.enterSteps": "Enter steps",
          "simPage.designExperiment": "Design experiment",
          "simPage.compareMode": "Compare mode",
          "simPage.analytics": "Analytics",
          "simPage.report": "Report",
          "simPage.export": "Export",
          "simPage.provider": "Provider",
          "simPage.globalKnowledge": "Global knowledge",
          "simPage.moreActions": "More actions",
          "simPage.selectProvider": "Select provider",
        } as Record<string, string>
      )[key] ?? key,
  }),
}));

describe("ContextToolbar", () => {
  beforeEach(() => {
    useSimulationStore.setState({
      activeTab: "workspace",
      selectedNodeId: "1",
      isGenerating: false,
      isCompareMode: false,
      isAutoAdvancing: false,
      autoAdvanceCurrent: 0,
      autoAdvanceTotal: 0,
      llmProviders: [],
      selectedProviderId: null,
      currentProviderId: null,
      advanceSimulation: vi.fn(),
      branchSimulation: vi.fn(),
      startAutoAdvance: vi.fn(),
      stopAutoAdvance: vi.fn(),
      toggleCompareMode: vi.fn(),
      setCompareTarget: vi.fn(),
      toggleExperimentDesigner: vi.fn(),
      toggleAnalytics: vi.fn(),
      toggleExport: vi.fn(),
      toggleReportModal: vi.fn(),
      setGlobalKnowledgeOpen: vi.fn(),
      setSelectedProvider: vi.fn(),
    } as never);
  });

  it("shows the overflow menu when the more actions button is pressed", () => {
    render(<ContextToolbar />);

    fireEvent.click(screen.getByRole("button", { name: "More actions" }));

    expect(screen.getByText("Analytics")).toBeInTheDocument();
    expect(screen.getByText("Report")).toBeInTheDocument();
    expect(screen.getByText("Export")).toBeInTheDocument();
    expect(screen.getByText("Global knowledge")).toBeInTheDocument();
  });

  it("keeps advance and steps in one control group with a single advance button", () => {
    render(<ContextToolbar />);

    const group = screen.getByLabelText("Advance controls");

    const advanceButton = within(group).getByRole("button", { name: "Advance node" });
    const stepsInput = within(group).getByRole("spinbutton", { name: "Enter steps" });

    expect(advanceButton).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Auto advance" })).not.toBeInTheDocument();
    expect(stepsInput).toBeInTheDocument();
    expect(group).toContainElement(advanceButton);
    expect(group).toContainElement(stepsInput);
  });
});
