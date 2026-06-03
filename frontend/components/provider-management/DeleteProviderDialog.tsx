// frontend/components/provider-management/DeleteProviderDialog.tsx
import type { Provider } from "../../services/providers";
import { Trans, useTranslation } from "react-i18next";

type DeleteProviderDialogProps = {
  provider: Provider | null;
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  isDeleting: boolean;
};

export function DeleteProviderDialog({
  provider,
  isOpen,
  onClose,
  onConfirm,
  isDeleting,
}: DeleteProviderDialogProps) {
  const { t } = useTranslation();
  if (!isOpen || !provider) return null;

  return (
    <div className="provider-dialog-overlay" role="presentation" onClick={onClose}>
      <div className="provider-dialog" role="dialog" aria-modal="true" onClick={(event) => event.stopPropagation()}>
        <h3 className="provider-dialog__title">{t("settings.providers.management.deleteDialog.title")}</h3>
        <p className="provider-dialog__description">
          <Trans
            i18nKey="settings.providers.management.deleteDialog.confirmMessage"
            values={{ name: provider.name }}
            components={{ strong: <strong /> }}
          />
        </p>
        <div className="provider-dialog__actions">
          <button type="button" className="provider-button provider-button--ghost" onClick={onClose}>
            {t("settings.providers.management.deleteDialog.cancel")}
          </button>
          <button type="button" className="provider-button provider-button--danger" onClick={onConfirm} disabled={isDeleting}>
            {isDeleting ? t("settings.providers.management.deleteDialog.deleting") : t("settings.providers.management.deleteDialog.delete")}
          </button>
        </div>
      </div>
    </div>
  );
}
