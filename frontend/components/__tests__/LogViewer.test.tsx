/**
 * These tests make sure the log viewer stays on its default layout
 * without showing inactive view-switch buttons.
 *
 * Each test checks one simple thing a person can see.
 */

import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { LogViewer } from "../LogViewer";
import { useSimulationStore } from "../../store";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string, options?: Record<string, unknown>) =>
      (
        {
          "components.logViewer.currentBranchFilter": "Current branch",
          "components.logViewer.searchPlaceholder": "Search logs",
          "components.logViewer.filter": "Filter",
          "components.logViewer.noMatchingLogs": "No matching logs found",
          "components.logViewer.noActivityYet": "No activity yet",
          "components.logViewer.showingRecords": `Showing ${options?.count ?? 0} records`,
          "components.logViewer.stepGroup": `Step ${options?.step ?? ""}`,
          "components.logViewer.setupGroup": "Setup",
          "components.logViewer.listView": "List view",
          "components.logViewer.cardView": "Card view",
          "components.logViewer.timelineView": "Timeline view",
        } as Record<string, string>
      )[key] ?? key,
  }),
}));

describe("LogViewer", () => {
  it("does not show the old view mode buttons", () => {
    useSimulationStore.setState({
      logs: [],
      nodes: [],
      selectedNodeId: "root",
      agents: [],
      currentSimulation: null,
    } as never);

    render(<LogViewer />);

    expect(screen.queryByTitle("List view")).not.toBeInTheDocument();
    expect(screen.queryByTitle("Card view")).not.toBeInTheDocument();
    expect(screen.queryByTitle("Timeline view")).not.toBeInTheDocument();
    expect(screen.getByText("No matching logs found")).toBeInTheDocument();
  });

  it("shows one step at a time when switching log groups", () => {
    useSimulationStore.setState({
      logs: [
        {
          id: "log-4",
          nodeId: "node-1",
          round: 4,
          type: "SYSTEM",
          content: "Agents acted in step 4",
          timestamp: "2026-05-21T10:00:00.000Z",
        },
        {
          id: "log-5",
          nodeId: "node-1",
          round: 5,
          type: "SYSTEM",
          content: "Agents acted in step 5",
          timestamp: "2026-05-21T10:05:00.000Z",
        },
      ],
      nodes: [{ id: "node-1", parentId: null, name: "Root", depth: 0, isLeaf: true }],
      selectedNodeId: "node-1",
      agents: [],
      currentSimulation: null,
    } as never);

    render(<LogViewer />);

    expect(screen.getByText("Agents acted in step 4")).toBeInTheDocument();
    expect(screen.queryByText("Agents acted in step 5")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Step 5/i }));

    expect(screen.getByText("Agents acted in step 5")).toBeInTheDocument();
    expect(screen.queryByText("Agents acted in step 4")).not.toBeInTheDocument();
  });

  it("lists step groups in ascending order", () => {
    useSimulationStore.setState({
      logs: [
        {
          id: "log-2",
          nodeId: "node-1",
          round: 2,
          type: "SYSTEM",
          content: "Agents acted in step 2",
          timestamp: "2026-05-21T10:05:00.000Z",
        },
        {
          id: "log-1",
          nodeId: "node-1",
          round: 1,
          type: "SYSTEM",
          content: "Agents acted in step 1",
          timestamp: "2026-05-21T10:00:00.000Z",
        },
      ],
      nodes: [{ id: "node-1", parentId: null, name: "Root", depth: 0, isLeaf: true }],
      selectedNodeId: "node-1",
      agents: [],
      currentSimulation: null,
    } as never);

    render(<LogViewer />);

    const stepButtons = screen.getAllByRole("button", { name: /Step /i });
    expect(stepButtons[0]).toHaveTextContent("Step 1");
    expect(stepButtons[1]).toHaveTextContent("Step 2");
  });
});
