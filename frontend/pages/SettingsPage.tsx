import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Bot,
  Database,
  FileStack,
  LogOut,
  Search,
  Shield,
  UserCircle2,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import {
  FilePlusIcon,
  TrashIcon,
} from "@radix-ui/react-icons";

import { AppSelect } from "../components/AppSelect";
import { TitleCard } from "../components/TitleCard";
import { ProviderManagementPage } from "../components/provider-management/ProviderManagementPage";
import {
  createSearchProvider,
  listSearchProviders,
  updateSearchProvider,
} from "../services/searchProviders";
import { deleteUpload, findOrphans, listUploads } from "../services/uploads";
import { useAuthStore } from "../store/auth";

type Tab = "profile" | "security" | "providers_llm" | "providers_search" | "files";

const getCapabilityRows = (t: (key: string) => string) => [
  {
    model: "gpt-4o-mini",
    context: "128k",
    input: "$0.15 / 1M",
    output: "$0.60 / 1M",
    modalities: "Text, Image",
    note: "settings.providers.modelNote.goodDefault",
  },
  {
    model: "gpt-4o",
    context: "128k",
    input: "$5.00 / 1M",
    output: "$15.00 / 1M",
    modalities: "Text, Image, Audio",
    note: "settings.providers.modelNote.fastLongContext",
  },
  {
    model: "gemini-1.5-flash",
    context: "1M",
    input: "$0.35 / 1M",
    output: "$1.05 / 1M",
    modalities: "Text, Image, Audio",
    note: "settings.providers.modelNote.fastLongContext",
  },
  {
    model: "gemini-1.5-pro",
    context: "2M",
    input: "$3.50 / 1M",
    output: "$10.50 / 1M",
    modalities: "Text, Image, Audio",
    note: "settings.providers.modelNote.goodDefault",
  },
];

function SettingsMetric({
  label,
  value,
  icon,
}: {
  label: string;
  value: string;
  icon: React.ReactNode;
}) {
  return (
    <div className="ss-settings-metric ss-inset">
      <div className="ss-settings-metric__icon">{icon}</div>
      <div>
        <div className="ss-settings-metric__label">{label}</div>
        <strong className="ss-settings-metric__value">{value}</strong>
      </div>
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="ss-settings-info-row">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

export function SettingsPage() {
  const { t } = useTranslation();
  const location = useLocation();
  const navigate = useNavigate();
  const user = useAuthStore((state) => state.user);
  const clearSession = useAuthStore((state) => state.clearSession);
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<Tab>("profile");
  const [orphanResult, setOrphanResult] = useState<{ orphaned: string[]; total: number } | null>(null);
  const [findingOrphans, setFindingOrphans] = useState(false);
  const [searchDraft, setSearchDraft] = useState({
    provider: "ddg",
    base_url: "",
    api_key: "",
    config: { region: "", safesearch: "moderate" } as Record<string, any>,
  });

  const searchProvidersQuery = useQuery({
    queryKey: ["searchProviders"],
    enabled: activeTab === "providers_search",
    queryFn: () => listSearchProviders(),
  });

  const filesQuery = useQuery({
    queryKey: ["uploads"],
    enabled: activeTab === "files",
    queryFn: () => listUploads(),
  });

  const deleteFile = useMutation({
    mutationFn: async (fileId: string) => deleteUpload(fileId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["uploads"] });
    },
  });

  const upsertSearch = useMutation({
    mutationFn: async () => {
      const searchProvider = (searchProvidersQuery.data ?? [])[0];
      if (searchProvider) {
        return updateSearchProvider(searchProvider.id, {
          provider: searchDraft.provider,
          base_url: searchDraft.base_url || null,
          api_key: searchDraft.api_key || null,
          config: searchDraft.config,
        });
      }
      return createSearchProvider({
        provider: searchDraft.provider,
        base_url: searchDraft.base_url || "",
        api_key: searchDraft.api_key || "",
        config: searchDraft.config,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["searchProviders"] });
    },
  });

  const searchProviders = searchProvidersQuery.data ?? [];
  const uploads = filesQuery.data ?? [];
  const searchProvider = searchProviders[0] || null;

  useEffect(() => {
    if (!searchProvider) return;
    setSearchDraft({
      provider: searchProvider.provider || "ddg",
      base_url: String(searchProvider.base_url || ""),
      api_key: "",
      config: (searchProvider as any).config || {},
    });
  }, [searchProvider]);

  const formatSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes}${t("settings.files.byte")}`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}${t("settings.files.kb")}`;
    return `${(bytes / (1024 * 1024)).toFixed(1)}${t("settings.files.mb")}`;
  };

  const formatDate = (timestamp: number): string => new Date(timestamp * 1000).toLocaleString();

  const tabItems = [
    {
      id: "profile" as const,
      title: t("settings.tabs.profile"),
      hint: t("settings.tabHints.profile"),
      icon: <UserCircle2 size={15} />,
    },
    {
      id: "security" as const,
      title: t("settings.tabs.security"),
      hint: t("settings.tabHints.security"),
      icon: <Shield size={15} />,
    },
    {
      id: "providers_llm" as const,
      title: t("settings.tabs.llmProviders"),
      hint: t("settings.tabHints.providersLlm"),
      icon: <Bot size={15} />,
    },
    {
      id: "providers_search" as const,
      title: t("settings.tabs.searchProviders") || t("settings.providers.searchTab"),
      hint: t("settings.tabHints.providersSearch"),
      icon: <Search size={15} />,
    },
    {
      id: "files" as const,
      title: t("settings.tabs.files"),
      hint: t("settings.tabHints.files"),
      icon: <FileStack size={15} />,
    },
  ];

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const nextTab = params.get("tab");
    if (
      nextTab === "profile" ||
      nextTab === "security" ||
      nextTab === "providers_llm" ||
      nextTab === "providers_search" ||
      nextTab === "files"
    ) {
      setActiveTab(nextTab);
    }
  }, [location.search]);

  const selectTab = (tab: Tab) => {
    setActiveTab(tab);
    const params = new URLSearchParams(location.search);
    params.set("tab", tab);
    navigate({ pathname: location.pathname, search: params.toString() }, { replace: true });
  };

  const renderProfile = () => (
    <div className="ss-settings-section">
      <section className="ss-settings-hero ss-surface-strong">
        <div>
          <div className="kicker">{t("settings.tabs.profile")}</div>
          <h2 className="section-title">{String(user?.full_name ?? user?.username ?? t("brand"))}</h2>
          <p className="panel-subtitle">{t("settings.subtitle")}</p>
        </div>
        <div className="ss-settings-info-grid">
          <InfoRow label={t("settings.profile.email")} value={String(user?.email ?? "—")} />
          <InfoRow label={t("settings.profile.username")} value={String(user?.username ?? "—")} />
          <InfoRow label={t("settings.profile.fullName")} value={String(user?.full_name ?? "—")} />
          <InfoRow label={t("settings.profile.organization")} value={String(user?.organization ?? "—")} />
        </div>
      </section>

      <div className="ss-settings-grid">
        <section className="card">
          <div className="panel-title">{t("settings.tabs.profile")}</div>
          <div className="panel-subtitle">{t("settings.profile.consistencyHint")}</div>
          <div className="ss-settings-info-grid">
            <InfoRow label={t("settings.profile.email")} value={String(user?.email ?? "—")} />
            <InfoRow label={t("settings.profile.username")} value={String(user?.username ?? "—")} />
            <InfoRow label={t("settings.profile.fullName")} value={String(user?.full_name ?? "—")} />
            <InfoRow label={t("settings.profile.organization")} value={String(user?.organization ?? "—")} />
          </div>
        </section>

        <section className="card">
          <div className="panel-title">{t("settings.workspaceTitle")}</div>
          <div className="panel-subtitle">{t("settings.workspaceHint")}</div>
          <div className="ss-settings-stack">
            <div className="ss-pill ss-pill--quiet">
              <Shield size={14} />
              <span>{t("settings.workspaceStatus.authenticatedAccess")}</span>
            </div>
            <div className="ss-pill ss-pill--quiet">
              <Database size={14} />
              <span>{t("settings.workspaceStatus.profileReuse")}</span>
            </div>
          </div>
        </section>
      </div>
    </div>
  );

  const renderSecurity = () => (
    <div className="ss-settings-grid">
      <section className="card">
        <div className="panel-title">{t("settings.security.sessionsTitle")}</div>
        <div className="panel-subtitle">{t("settings.security.placeholder")}</div>
        <button type="button" className="ss-button-danger" onClick={() => clearSession()}>
          <LogOut size={15} />
          <span>{t("settings.security.signoutAll")}</span>
        </button>
      </section>

      <section className="card">
        <div className="panel-title">{t("settings.security.controlTitle")}</div>
        <div className="panel-subtitle">{t("settings.security.controlHint")}</div>
        <div className="ss-settings-note">{t("settings.security.authFlowNote")}</div>
        </section>
    </div>
  );

  const renderProviders = () => (
    <ProviderManagementPage />
  );

  const renderSearchProviders = () => (
    <div className="ss-settings-grid ss-settings-grid--split">
      <section className="card">
        <div className="panel-title">{t("settings.providers.searchTitle")}</div>
        <div className="panel-subtitle">{t("settings.providers.searchAlignmentHint")}</div>
        <div className="ss-settings-info-grid">
          <InfoRow label={t("settings.providers.fields.provider")} value={searchProvider?.provider || "—"} />
          <InfoRow label={t("settings.providers.fields.baseUrl")} value={searchProvider?.base_url || "—"} />
        </div>
      </section>

      <section className="card">
        <div className="panel-title">{t("settings.providers.setSearchProvider")}</div>
        <div className="ss-settings-form-grid">
          <label>
            <span className="ss-form-label">{t("settings.providers.fields.provider")}</span>
            <AppSelect
              value={searchDraft.provider}
              options={[
                { value: "ddg", label: t("settings.providers.searchEngine.ddg") },
                { value: "serpapi", label: t("settings.providers.searchEngine.serpapi") },
                { value: "serper", label: t("settings.providers.searchEngine.serper") },
                { value: "tavily", label: t("settings.providers.searchEngine.tavily") },
                { value: "mock", label: "Mock" },
              ]}
              onChange={(value) => setSearchDraft((prev) => ({ ...prev, provider: value }))}
            />
          </label>

          {(searchDraft.provider === "serpapi" ||
            searchDraft.provider === "serper" ||
            searchDraft.provider === "tavily") && (
            <>
              <label>
                <span className="ss-form-label">{t("settings.providers.fields.baseUrl")}</span>
                <input
                  value={searchDraft.base_url}
                  onChange={(event) =>
                    setSearchDraft((prev) => ({ ...prev, base_url: event.target.value }))
                  }
                />
              </label>
              <label>
                <span className="ss-form-label">{t("settings.providers.fields.apiKey")}</span>
                <input
                  value={searchDraft.api_key}
                  onChange={(event) =>
                    setSearchDraft((prev) => ({ ...prev, api_key: event.target.value }))
                  }
                />
              </label>
            </>
          )}

          {searchDraft.provider === "ddg" && (
            <>
              <label>
                <span className="ss-form-label">{t("settings.providers.search.region")}</span>
                <input
                  value={String((searchDraft.config as any).region || "")}
                  onChange={(event) =>
                    setSearchDraft((prev) => ({
                      ...prev,
                      config: { ...(prev.config || {}), region: event.target.value },
                    }))
                  }
                />
              </label>
              <label>
                <span className="ss-form-label">{t("settings.providers.search.safeSearch")}</span>
                <input
                  value={String((searchDraft.config as any).safesearch || "moderate")}
                  onChange={(event) =>
                    setSearchDraft((prev) => ({
                      ...prev,
                      config: { ...(prev.config || {}), safesearch: event.target.value },
                    }))
                  }
                />
              </label>
            </>
          )}

          {searchDraft.provider === "tavily" && (
            <>
              <label>
                <span className="ss-form-label">{t("settings.providers.search.searchDepth")}</span>
                <AppSelect
                  value={String((searchDraft.config as any).search_depth || "basic")}
                  options={[
                    { value: "basic", label: "basic" },
                    { value: "advanced", label: "advanced" },
                  ]}
                  onChange={(value) =>
                    setSearchDraft((prev) => ({
                      ...prev,
                      config: { ...(prev.config || {}), search_depth: value },
                    }))
                  }
                />
              </label>
              <label>
                <span className="ss-form-label">{t("settings.providers.search.topic")}</span>
                <input
                  value={String((searchDraft.config as any).topic || "")}
                  onChange={(event) =>
                    setSearchDraft((prev) => ({
                      ...prev,
                      config: { ...(prev.config || {}), topic: event.target.value },
                    }))
                  }
                />
              </label>
              <label>
                <span className="ss-form-label">{t("settings.providers.search.days")}</span>
                <input
                  type="number"
                  min={1}
                  value={Number((searchDraft.config as any).days || 7)}
                  onChange={(event) =>
                    setSearchDraft((prev) => ({
                      ...prev,
                      config: { ...(prev.config || {}), days: Number(event.target.value || 0) },
                    }))
                  }
                />
              </label>
              <label>
                <span className="ss-form-label">{t("settings.providers.search.includeDomains")}</span>
                <input
                  value={String((searchDraft.config as any).include_domains || "")}
                  onChange={(event) =>
                    setSearchDraft((prev) => ({
                      ...prev,
                      config: { ...(prev.config || {}), include_domains: event.target.value },
                    }))
                  }
                />
              </label>
            </>
          )}
        </div>

        <button
          type="button"
          className="ss-button"
          onClick={() => upsertSearch.mutate()}
          disabled={upsertSearch.isPending}
        >
          {upsertSearch.isPending ? <span className="spinner" aria-hidden /> : <FilePlusIcon />}
          <span>{t("settings.providers.save")}</span>
        </button>
      </section>
    </div>
  );

  const renderFiles = () => (
    <div className="ss-settings-section">
      <div className="ss-settings-grid">
        <SettingsMetric
          label={t("settings.files.metrics.files")}
          value={String(uploads.length)}
          icon={<FileStack size={16} />}
        />
        <SettingsMetric
          label={t("settings.files.metrics.orphanScan")}
          value={orphanResult ? String(orphanResult.orphaned.length) : "—"}
          icon={<Database size={16} />}
        />
      </div>

      <section className="card">
        <div className="panel-title">{t("settings.files.title")}</div>
        <div className="panel-subtitle">{t("settings.files.description")}</div>

        {filesQuery.isLoading ? <div>{t("settings.files.loading")}</div> : null}
        {filesQuery.error ? <div>{t("settings.files.error")}</div> : null}

        {uploads.length ? (
          <div className="ss-data-table-wrap">
            <table className="ss-data-table">
              <thead>
                <tr>
                  <th>{t("settings.files.table.filename")}</th>
                  <th>{t("settings.files.table.type")}</th>
                  <th>{t("settings.files.table.size")}</th>
                  <th>{t("settings.files.table.created")}</th>
                  <th>{t("settings.files.table.actions")}</th>
                </tr>
              </thead>
              <tbody>
                {uploads.map((file) => (
                  <tr key={file.id}>
                    <td title={file.filename}>{file.filename}</td>
                    <td>{file.type || "-"}</td>
                    <td>{formatSize(file.size)}</td>
                    <td>{formatDate(file.created)}</td>
                    <td className="ss-data-table__actions">
                      <button
                        type="button"
                        className="icon-button square"
                        title={t("settings.files.delete")}
                        aria-label={t("settings.files.delete")}
                        onClick={() => {
                          if (window.confirm(t("settings.files.deleteConfirm"))) {
                            deleteFile.mutate(file.id);
                          }
                        }}
                        disabled={deleteFile.isPending}
                      >
                        <TrashIcon />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}

        {!uploads.length && !filesQuery.isLoading ? (
          <div className="ss-empty-state ss-inset">
            <div className="panel-title">{t("settings.files.empty")}</div>
            <div className="panel-subtitle">{t("settings.files.emptyHint")}</div>
          </div>
        ) : null}
      </section>

      <section className="card">
        <div className="panel-title">{t("settings.files.maintenanceTitle")}</div>
        <div className="panel-subtitle">{t("settings.files.maintenanceHint")}</div>
        <div className="ss-settings-action-row">
          <button
            type="button"
            className="ss-button-secondary"
            onClick={async () => {
              setFindingOrphans(true);
              const result = await findOrphans();
              setOrphanResult(result);
              setFindingOrphans(false);
            }}
            disabled={findingOrphans}
          >
            {findingOrphans ? "…" : t("settings.files.findOrphans")}
          </button>
          <span className="panel-subtitle">
            {orphanResult
              ? orphanResult.orphaned.length > 0
                ? t("settings.files.orphansFound", { count: orphanResult.orphaned.length })
                : t("settings.files.noOrphans")
              : t("settings.files.noOrphans")}
          </span>
        </div>
      </section>
    </div>
  );

  const renderActiveTab = () => {
    if (activeTab === "profile") return renderProfile();
    if (activeTab === "security") return renderSecurity();
    if (activeTab === "providers_llm") return renderProviders();
    if (activeTab === "providers_search") return renderSearchProviders();
    return renderFiles();
  };

  return (
    <div className="ss-product-page ss-product-page--settings scroll-panel">
      <TitleCard title={t("settings.title")} />

      <div className="tab-layout ss-settings-page__layout">
        <nav className="tab-nav ss-settings-page__nav">
          {tabItems.map((item) => (
            <button
              key={item.id}
              type="button"
              className={`tab-button ss-settings-page__tab ${activeTab === item.id ? "active" : ""}`}
              onClick={() => selectTab(item.id)}
            >
              <span className="ss-settings-page__tab-icon">{item.icon}</span>
              <span className="ss-settings-page__tab-copy">
                <strong>{item.title}</strong>
                <span>{item.hint}</span>
              </span>
            </button>
          ))}
        </nav>
        <section className="ss-settings-page__content">{renderActiveTab()}</section>
      </div>
    </div>
  );
}
