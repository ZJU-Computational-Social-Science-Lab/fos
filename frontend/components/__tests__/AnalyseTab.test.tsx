/**
 * These tests make sure the analysis page keeps overview and compare
 * diff together under the analysis area.
 *
 * Each test checks one visible tab switch.
 */

import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AnalyseTab } from "../AnalyseTab";
import { useSimulationStore } from "../../store";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) =>
      (
        {
          "components.analyseTab.overview": "Overview",
          "components.analyseTab.compareDiff": "Compare diff",
          "simPage.tabs.analyse": "Analyse",
          "simPage.analytics": "Analytics",
          "simPage.report": "Report",
        } as Record<string, string>
      )[key] ?? key,
  }),
}));

vi.mock("../ComparisonView", () => ({
  ComparisonView: () => <div>Compare Diff Panel</div>,
}));

describe("AnalyseTab", () => {
  beforeEach(() => {
    useSimulationStore.setState({
      agents: [],
      logs: [],
      toggleAnalytics: vi.fn(),
      toggleReportModal: vi.fn(),
    } as never);
  });

  it("shows the overview first", () => {
    render(<AnalyseTab />);

    expect(screen.getByText("Overview")).toBeInTheDocument();
    expect(screen.getByText("Compare diff")).toBeInTheDocument();
    expect(screen.getByText("Analyse")).toBeInTheDocument();
  });

  it("switches to compare diff", () => {
    render(<AnalyseTab />);

    fireEvent.click(screen.getByRole("button", { name: "Compare diff" }));

    expect(screen.getByText("Compare Diff Panel")).toBeInTheDocument();
  });
});
