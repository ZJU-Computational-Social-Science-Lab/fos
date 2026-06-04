/**
 * This file shows a simple analysis area for the simulation page.
 *
 * AnalyseTab shows overview stats and also gives compare diff its own
 * home inside the analysis area.
 */

import React from "react";
import { useTranslation } from "react-i18next";
import { BarChart3, GitCompareArrows } from "lucide-react";
import { ComparisonView } from "./ComparisonView";
import { ResultsView, ResultsLabels } from "./results/ResultsView";

type AnalyseView = "results" | "compare";

export const AnalyseTab: React.FC = () => {
  const { t, i18n } = useTranslation();
  const [activeView, setActiveView] = React.useState<AnalyseView>("results");

  const language: "en" | "zh" = i18n.language.startsWith("zh") ? "zh" : "en";
  const labels: ResultsLabels = {
    noData: t("results.noData"),
    generate: t("results.generate"),
    generating: t("results.generating"),
    metric: t("results.metric"),
    exportCsv: t("results.exportCsv"),
    exportReport: t("results.exportReport"),
    noActivity: t("results.noActivity"),
    reportSummary: t("results.reportSummary"),
    reportNoSummary: t("results.reportNoSummary"),
    reportFinalValues: t("results.reportFinalValues"),
    reportAgent: t("results.reportAgent"),
    reportFinalValue: t("results.reportFinalValue"),
  };

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
          onClick={() => setActiveView("results")}
          className="flex items-center gap-2 px-4 py-2 text-sm border-b-2"
          style={{
            borderColor:
              activeView === "results"
                ? "var(--ss-brand-primary)"
                : "transparent",
            color:
              activeView === "results"
                ? "var(--ss-brand-primary)"
                : "var(--ss-workspace-text)",
          }}
        >
          <BarChart3 size={16} />
          {t("components.analyseTab.results")}
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
        <div className="h-full overflow-auto">
          <ResultsView labels={labels} language={language} />
        </div>
      )}
    </div>
  );
};
