/**
 * Context-sensitive toolbar for the simulation page.
 *
 * Renders the compact top controls used by the workspace page.
 *
 * The main simulation controls stay visible here, while lower-priority
 * actions live behind a small overflow menu.
 *
 * Uses the design-system Button component for consistent styling.
 *
 * Exports: ContextToolbar
 */

import React from "react";
import { useTranslation } from "react-i18next";
import {
  Play,
  GitFork,
  Loader2,
  BarChart2,
  Download,
  Globe,
  MoreHorizontal,
  FileText,
  Square,
} from "lucide-react";
import { useSimulationStore } from "../store";
import { Button } from "./ui/button";

const ContextToolbar: React.FC = () => {
  const { t } = useTranslation();

  // Tab selection
  const activeTab = useSimulationStore((s) => s.activeTab);

  // Advance / Branch / Auto-advance
  const branchSimulation = useSimulationStore((s) => s.branchSimulation);
  const isGenerating = useSimulationStore((s) => s.isGenerating);
  const isAutoAdvancing = useSimulationStore((s) => s.isAutoAdvancing);
  const autoAdvanceCurrent = useSimulationStore((s) => s.autoAdvanceCurrent);
  const autoAdvanceTotal = useSimulationStore((s) => s.autoAdvanceTotal);
  const startAutoAdvance = useSimulationStore((s) => s.startAutoAdvance);
  const stopAutoAdvance = useSimulationStore((s) => s.stopAutoAdvance);

  // Node readiness — disable actions when selected node is a placeholder
  const selectedNodeId = useSimulationStore((s) => s.selectedNodeId);
  const selectedNodeIsReady = Number.isFinite(Number(selectedNodeId));

  const isCompareMode = useSimulationStore((s) => s.isCompareMode);

  // Panel toggles
  const toggleAnalytics = useSimulationStore((s) => s.toggleAnalytics);
  const toggleExport = useSimulationStore((s) => s.toggleExport);
  const toggleReportModal = useSimulationStore((s) => s.toggleReportModal);
  const setGlobalKnowledgeOpen = useSimulationStore((s) => s.setGlobalKnowledgeOpen);

  // Provider
  const llmProviders = useSimulationStore((s) => s.llmProviders);
  const selectedProviderId = useSimulationStore((s) => s.selectedProviderId);
  const currentProviderId = useSimulationStore((s) => s.currentProviderId);
  const setSelectedProvider = useSimulationStore((s) => s.setSelectedProvider);

  const [advanceSteps, setAdvanceSteps] = React.useState(1);
  const [isMoreMenuOpen, setIsMoreMenuOpen] = React.useState(false);

  const providerSelection = selectedProviderId ?? currentProviderId ?? null;

  // ---- simTree tab toolbar ----
  const simTreeToolbar = (
    <>
      <div className="flex items-center gap-2">
        <Button
          variant="outline"
          size="sm"
          onClick={branchSimulation}
          disabled={isGenerating || isCompareMode || !selectedNodeIsReady}
        >
          <GitFork size={14} />
          {t('simPage.branch')}
        </Button>
      </div>
    </>
  );

  const moreMenu = (
    <div className="relative">
      <Button
        type="button"
        variant="outline"
        size="sm"
        onClick={() => setIsMoreMenuOpen((current) => !current)}
        aria-label={t("simPage.moreActions")}
      >
        <MoreHorizontal size={14} />
      </Button>

      {isMoreMenuOpen && (
        <div
          className="absolute right-0 top-full mt-2 w-72 rounded-2xl border shadow-xl p-3 z-20"
          style={{
            background: "var(--ss-workspace-surface)",
            borderColor: "var(--ss-workspace-border)",
          }}
        >
          <div className="space-y-2">
            <div
              className="rounded-xl border p-3 space-y-2"
              style={{ borderColor: "var(--ss-workspace-border)" }}
            >
              <div className="text-xs font-medium" style={{ color: "var(--ss-workspace-muted)" }}>
                {t("simPage.provider")}
              </div>
              <select
                value={providerSelection ?? ""}
                onChange={(e) => {
                  const val = e.target.value;
                  setSelectedProvider(val ? Number(val) : null);
                }}
                className="w-full border rounded-full px-3 py-2 text-xs focus:outline-none focus:ring-1 focus:ring-[var(--ss-brand-primary)]"
                style={{ background: "var(--ss-surface)", borderColor: "var(--ss-border)" }}
              >
                <option value="">{t("simPage.selectProvider")}</option>
                {llmProviders.map((provider) => (
                  <option key={provider.id} value={provider.id}>
                    {provider.name || provider.provider}{" "}
                    {provider.model ? `(${provider.model})` : ""}
                  </option>
                ))}
              </select>
            </div>

            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setGlobalKnowledgeOpen(true);
                setIsMoreMenuOpen(false);
              }}
              className="w-full justify-start"
            >
              <Globe size={14} />
              {t("simPage.globalKnowledge")}
            </Button>

            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                toggleAnalytics(true);
                setIsMoreMenuOpen(false);
              }}
              className="w-full justify-start"
            >
              <BarChart2 size={14} />
              {t("simPage.analytics")}
            </Button>

            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                toggleReportModal(true);
                setIsMoreMenuOpen(false);
              }}
              className="w-full justify-start"
            >
              <FileText size={14} />
              {t("simPage.report")}
            </Button>

            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                toggleExport(true);
                setIsMoreMenuOpen(false);
              }}
              className="w-full justify-start"
            >
              <Download size={14} />
              {t("simPage.export")}
            </Button>
          </div>
        </div>
      )}
    </div>
  );

  return (
    <div className="flex items-center gap-3 px-4 py-3 border-b min-h-[56px]" style={{ background: 'var(--ss-workspace-toolbar)', borderColor: 'var(--ss-border)' }}>
      {activeTab === 'workspace' && (
        <>
          {simTreeToolbar}
          <div className="flex-1" />
          <div
            role="group"
            aria-label="Advance controls"
            className="flex items-center gap-2 rounded-2xl border px-2 py-2 shadow-sm"
            style={{
              background: "var(--ss-workspace-surface)",
              borderColor: "var(--ss-workspace-border)",
            }}
          >
            <div
              className="flex items-center gap-2 rounded-xl border px-3 py-2"
              style={{
                background: "var(--ss-workspace-bg)",
                borderColor: "var(--ss-workspace-border)",
              }}
            >
              <input
                type="number"
                min={1}
                max={100}
                value={advanceSteps}
                onChange={(e) => {
                  const v = parseInt(e.target.value, 10);
                  if (!isNaN(v)) setAdvanceSteps(Math.min(100, Math.max(1, v)));
                }}
                disabled={isAutoAdvancing || isGenerating || isCompareMode}
                className="w-16 bg-transparent text-sm text-center focus:outline-none disabled:opacity-50"
                title={t('simPage.enterSteps')}
              />
              <span className="text-xs font-medium" style={{ color: "var(--ss-workspace-muted)" }}>
                steps
              </span>
            </div>

            {isAutoAdvancing ? (
              <Button
                variant="destructive"
                size="sm"
                onClick={() => stopAutoAdvance()}
                className="min-w-[132px]"
              >
                <Square size={14} />
                {t('simPage.stop')}
              </Button>
            ) : (
              <Button
                size="sm"
                onClick={() => startAutoAdvance(advanceSteps)}
                disabled={isGenerating || isCompareMode || !selectedNodeIsReady}
                className={`min-w-[148px] ${isGenerating ? "!bg-[var(--ss-text-muted)] !text-[var(--ss-neutral-0)] !shadow-none" : ""}`}
              >
                <Play size={14} fill="currentColor" />
                {t('simPage.advance')}
              </Button>
            )}
          </div>
          {isAutoAdvancing && (
            <span className="text-xs px-2" style={{ color: 'var(--ss-text-muted)' }}>
              {t('simPage.advancingProgress', {
                current: autoAdvanceCurrent,
                total: autoAdvanceTotal,
              })}
            </span>
          )}
          {moreMenu}
        </>
      )}
    </div>
  );
};

export default ContextToolbar;
