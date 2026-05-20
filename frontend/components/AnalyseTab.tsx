/**
 * This file shows a simple analysis area for the simulation page.
 *
 * AnalyseTab shows overview stats and also gives compare diff its own
 * home inside the analysis area.
 */

import React from "react";
import { useTranslation } from "react-i18next";
import { BarChart3, FileText, GitCompareArrows, TrendingUp } from "lucide-react";
import { useSimulationStore } from "../store";
import { ComparisonView } from "./ComparisonView";

type AnalyseView = "overview" | "compare";

export const AnalyseTab: React.FC = () => {
  const { t } = useTranslation();
  const [activeView, setActiveView] = React.useState<AnalyseView>("overview");
  const agents = useSimulationStore((state) => state.agents);
  const logs = useSimulationStore((state) => state.logs);
  const toggleAnalytics = useSimulationStore((state) => state.toggleAnalytics);
  const toggleReportModal = useSimulationStore(
    (state) => state.toggleReportModal
  );

  const availableMetrics =
    agents.length > 0 && agents[0].history
      ? Object.keys(agents[0].history)
      : [];

  return (
    <div
      className="h-full flex flex-col"
      style={{ background: "var(--ss-workspace-bg)" }}
    >
      <div
        className="flex items-center gap-2 border-b px-5 pt-4"
        style={{ borderColor: "var(--ss-workspace-border)" }}
      >
        <button
          type="button"
          onClick={() => setActiveView("overview")}
          className="flex items-center gap-2 px-4 py-2 text-sm border-b-2"
          style={{
            borderColor:
              activeView === "overview"
                ? "var(--ss-brand-primary)"
                : "transparent",
            color:
              activeView === "overview"
                ? "var(--ss-brand-primary)"
                : "var(--ss-workspace-text)",
          }}
        >
          <BarChart3 size={16} />
          {t("components.analyseTab.overview")}
        </button>
        <button
          type="button"
          onClick={() => setActiveView("compare")}
          className="flex items-center gap-2 px-4 py-2 text-sm border-b-2"
          style={{
            borderColor:
              activeView === "compare"
                ? "var(--ss-brand-primary)"
                : "transparent",
            color:
              activeView === "compare"
                ? "var(--ss-brand-primary)"
                : "var(--ss-workspace-text)",
          }}
        >
          <GitCompareArrows size={16} />
          {t("components.analyseTab.compareDiff")}
        </button>
      </div>

      {activeView === "compare" ? (
        <div className="flex-1 overflow-hidden">
          <ComparisonView />
        </div>
      ) : (
        <div className="h-full overflow-auto p-6">
          <div className="max-w-3xl mx-auto">
            <div className="flex items-center gap-3 mb-6">
              <BarChart3
                size={22}
                style={{ color: "var(--ss-brand-primary)" }}
              />
              <h2
                className="text-lg font-bold"
                style={{ color: "var(--ss-workspace-text)" }}
              >
                {t("simPage.tabs.analyse")}
              </h2>
            </div>

            <div className="grid grid-cols-3 gap-4 mb-6">
              <div
                className="rounded-lg border p-4"
                style={{
                  background: "var(--ss-workspace-surface)",
                  borderColor: "var(--ss-workspace-border)",
                }}
              >
                <div
                  className="text-xs mb-1"
                  style={{ color: "var(--ss-workspace-muted)" }}
                >
                  Agents
                </div>
                <div
                  className="text-2xl font-bold"
                  style={{ color: "var(--ss-workspace-text)" }}
                >
                  {agents.length}
                </div>
              </div>
              <div
                className="rounded-lg border p-4"
                style={{
                  background: "var(--ss-workspace-surface)",
                  borderColor: "var(--ss-workspace-border)",
                }}
              >
                <div
                  className="text-xs mb-1"
                  style={{ color: "var(--ss-workspace-muted)" }}
                >
                  Log entries
                </div>
                <div
                  className="text-2xl font-bold"
                  style={{ color: "var(--ss-workspace-text)" }}
                >
                  {logs.length}
                </div>
              </div>
              <div
                className="rounded-lg border p-4"
                style={{
                  background: "var(--ss-workspace-surface)",
                  borderColor: "var(--ss-workspace-border)",
                }}
              >
                <div
                  className="text-xs mb-1"
                  style={{ color: "var(--ss-workspace-muted)" }}
                >
                  Metrics
                </div>
                <div
                  className="text-2xl font-bold"
                  style={{ color: "var(--ss-workspace-text)" }}
                >
                  {availableMetrics.length}
                </div>
              </div>
            </div>

            <div className="flex gap-3">
              <button
                onClick={() => toggleAnalytics(true)}
                className="flex items-center gap-2 px-4 py-2 rounded-lg border text-sm font-medium transition-colors hover:opacity-80"
                style={{
                  background: "var(--ss-brand-soft)",
                  color: "var(--ss-brand-primary)",
                  borderColor: "var(--ss-brand-primary)",
                }}
              >
                <TrendingUp size={16} />
                {t("simPage.analytics")}
              </button>
              <button
                onClick={() => toggleReportModal(true)}
                className="flex items-center gap-2 px-4 py-2 rounded-lg border text-sm font-medium transition-colors hover:opacity-80"
                style={{
                  background: "var(--ss-workspace-surface)",
                  color: "var(--ss-workspace-text)",
                  borderColor: "var(--ss-workspace-border)",
                }}
              >
                <FileText size={16} />
                {t("simPage.report")}
              </button>
            </div>

            {availableMetrics.length > 0 && (
              <div className="mt-6">
                <h3
                  className="text-sm font-semibold mb-3"
                  style={{ color: "var(--ss-workspace-muted)" }}
                >
                  Available metrics
                </h3>
                <div className="flex flex-wrap gap-2">
                  {availableMetrics.map((metric) => (
                    <span
                      key={metric}
                      className="px-3 py-1 rounded-full text-xs font-medium"
                      style={{
                        background: "var(--ss-brand-soft)",
                        color: "var(--ss-brand-primary)",
                      }}
                    >
                      {metric}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
