// frontend/components/provider-management/ProviderDrawerForm.tsx
import { useEffect, useState } from "react";
import { Eye, EyeOff, X } from "lucide-react";
import { useTranslation } from "react-i18next";
import type { Provider } from "../../services/providers";
import type { ProviderFormValues } from "./ProviderManagementPage";

type ProviderDrawerFormProps = {
  isOpen: boolean;
  mode: "create" | "edit";
  provider: Provider | null;
  initialValues: ProviderFormValues;
  onClose: () => void;
  onSubmit: (values: ProviderFormValues) => void;
  isSaving: boolean;
};

export function ProviderDrawerForm({
  isOpen,
  mode,
  provider,
  initialValues,
  onClose,
  onSubmit,
  isSaving,
}: ProviderDrawerFormProps) {
  const { t } = useTranslation();
  const [values, setValues] = useState<ProviderFormValues>(initialValues);
  const [showApiKey, setShowApiKey] = useState(false);

  useEffect(() => {
    setValues(initialValues);
    setShowApiKey(false);
  }, [initialValues, isOpen]);

  if (!isOpen) return null;

  const isGemini = values.provider === "gemini";
  const title =
    mode === "create"
      ? t("settings.providers.providerForm.newLlmTitle")
      : t("settings.providers.providerForm.editLlmTitle", { name: provider?.name ?? "" });

  return (
    <div className="provider-drawer-shell" role="presentation" onClick={onClose}>
      <aside className="provider-drawer" role="dialog" aria-modal="true" onClick={(event) => event.stopPropagation()}>
        <div className="provider-drawer__header">
          <div>
            <h2 className="provider-drawer__title">{title}</h2>
            <p className="provider-drawer__subtitle">
              {isGemini
                ? t("settings.providers.providerForm.geminiAccessConfig")
                : t("settings.providers.providerForm.openaiCompatibleAccessConfig")}
            </p>
          </div>
          <button type="button" className="provider-drawer__close" onClick={onClose} aria-label={t("common.cancel")}>
            <X size={18} />
          </button>
        </div>

        <form
          className="provider-drawer__form"
          onSubmit={(event) => {
            event.preventDefault();
            onSubmit(values);
          }}
        >
          <div className="provider-form-grid">
            <label className="provider-field">
              <span className="provider-field__label">{t("settings.providers.providerForm.llmNameRequired")}</span>
              <input
                className="provider-field__input"
                value={values.name}
                onChange={(event) => setValues((current) => ({ ...current, name: event.target.value }))}
                placeholder={t("settings.providers.providerForm.llmNamePlaceholder")}
                required
              />
            </label>

            <label className="provider-field">
              <span className="provider-field__label">{t("settings.providers.providerForm.providerTypeRequired")}</span>
              <select
                className="provider-field__input"
                value={values.provider}
                onChange={(event) => setValues((current) => ({ ...current, provider: event.target.value as ProviderFormValues["provider"] }))}
              >
                <option value="openai-compatible">{t("settings.providers.type.openai")}</option>
                <option value="gemini">{t("settings.providers.type.gemini")}</option>
              </select>
            </label>

            {!isGemini ? (
              <label className="provider-field provider-field--full">
                <span className="provider-field__label">{t("settings.providers.providerForm.baseUrlRequired")}</span>
                <input
                  className="provider-field__input"
                  value={values.base_url}
                  onChange={(event) => setValues((current) => ({ ...current, base_url: event.target.value }))}
                  placeholder={t("settings.providers.providerForm.baseUrlPlaceholder")}
                  required
                />
              </label>
            ) : null}

            <label className="provider-field provider-field--full">
              <span className="provider-field__label">{t("settings.providers.providerForm.apiKeyRequired")}</span>
              <div className="provider-field__secret-row">
                <input
                  className="provider-field__input"
                  type={showApiKey ? "text" : "password"}
                  value={values.api_key}
                  onChange={(event) => setValues((current) => ({ ...current, api_key: event.target.value }))}
                  placeholder={t("settings.providers.providerForm.apiKeyPlaceholder")}
                  required={mode === "create"}
                />
                <button
                  type="button"
                  className="provider-field__secret-toggle"
                  onClick={() => setShowApiKey((current) => !current)}
                  aria-label={
                    showApiKey
                      ? t("settings.providers.providerForm.hideApiKey")
                      : t("settings.providers.providerForm.showApiKey")
                  }
                >
                  {showApiKey ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </label>

            <label className="provider-field provider-field--full">
              <span className="provider-field__label">{t("settings.providers.providerForm.defaultModel")}</span>
              <input
                className="provider-field__input"
                value={values.model}
                onChange={(event) => setValues((current) => ({ ...current, model: event.target.value }))}
                placeholder={
                  isGemini
                    ? t("settings.providers.providerForm.defaultModelPlaceholderGemini")
                    : t("settings.providers.providerForm.defaultModelPlaceholderOpenai")
                }
              />
            </label>
          </div>

          <details className="provider-advanced">
            <summary className="provider-advanced__summary">{t("settings.providers.providerForm.advancedSettings")}</summary>
            <div className="provider-advanced__body">
              <div className="provider-advanced__grid">
                <label className="provider-field">
                  <span className="provider-field__label">{t("settings.providers.providerForm.temperature")}</span>
                  <input
                    className="provider-field__input"
                    value={values.temperature}
                    onChange={(event) => setValues((current) => ({ ...current, temperature: event.target.value }))}
                    placeholder={t("settings.providers.providerForm.exampleDecimal07")}
                    inputMode="decimal"
                  />
                </label>

                <label className="provider-field">
                  <span className="provider-field__label">{t("settings.providers.providerForm.topP")}</span>
                  <input
                    className="provider-field__input"
                    value={values.top_p}
                    onChange={(event) => setValues((current) => ({ ...current, top_p: event.target.value }))}
                    placeholder={t("settings.providers.providerForm.exampleDecimal10")}
                    inputMode="decimal"
                  />
                </label>

                <label className="provider-field">
                  <span className="provider-field__label">{t("settings.providers.providerForm.maxTokens")}</span>
                  <input
                    className="provider-field__input"
                    value={values.max_tokens}
                    onChange={(event) => setValues((current) => ({ ...current, max_tokens: event.target.value }))}
                    placeholder={t("settings.providers.providerForm.exampleMaxTokens")}
                    inputMode="numeric"
                  />
                </label>

                <label className="provider-field">
                  <span className="provider-field__label">{t("settings.providers.providerForm.responseFormat")}</span>
                  <input
                    className="provider-field__input"
                    value={values.response_format}
                    onChange={(event) => setValues((current) => ({ ...current, response_format: event.target.value }))}
                    placeholder={t("settings.providers.providerForm.exampleJsonObject")}
                  />
                </label>

                <label className="provider-field provider-field--full">
                  <span className="provider-field__label">{t("settings.providers.providerForm.timeoutMs")}</span>
                  <input
                    className="provider-field__input"
                    value={values.timeout_ms}
                    onChange={(event) => setValues((current) => ({ ...current, timeout_ms: event.target.value }))}
                    placeholder={t("settings.providers.providerForm.exampleTimeoutMs")}
                    inputMode="numeric"
                  />
                </label>
              </div>

              <label className="provider-field provider-field--full">
                <span className="provider-field__label">{t("settings.providers.providerForm.customEndpoint")}</span>
                <input
                  className="provider-field__input"
                  value={values.custom_endpoint}
                  onChange={(event) => setValues((current) => ({ ...current, custom_endpoint: event.target.value }))}
                  placeholder={t("settings.providers.providerForm.optional")}
                />
              </label>

              <label className="provider-field provider-field--full">
                <span className="provider-field__label">{t("settings.providers.providerForm.headersMetadata")}</span>
                <textarea
                  className="provider-field__textarea"
                  value={values.metadata}
                  onChange={(event) => setValues((current) => ({ ...current, metadata: event.target.value }))}
                  placeholder={t("settings.providers.providerForm.optional")}
                  rows={4}
                />
              </label>

              <p className="provider-advanced__hint">{t("settings.providers.providerForm.advancedHint")}</p>
            </div>
          </details>

          <div className="provider-drawer__footer">
            <button type="button" className="provider-button provider-button--ghost" onClick={onClose}>
              {t("common.cancel")}
            </button>
            <button type="submit" className="provider-button provider-button--primary" disabled={isSaving}>
              {isSaving ? t("settings.providers.providerForm.saving") : t("settings.providers.providerForm.save")}
            </button>
          </div>
        </form>
      </aside>
    </div>
  );
}
