// frontend/pages/DocsPage.tsx
/**
 * Documentation page component.
 *
 * Displays documentation content with a sidebar navigation and
 * markdown rendering. Supports multiple languages and loads
 * markdown content dynamically based on current language.
 *
 * Exports: DocsPage component
 */

import React, { useState, useMemo } from "react";
import { TitleCard } from "../components/TitleCard";
import { MarkdownRenderer } from "../components/MarkdownRenderer";
import { DocsSidebar } from "../components/DocsSidebar";
import { useTranslation } from "react-i18next";

// Import markdown files
import docsEn from "../docs/docs-en.md?raw";
import docsZh from "../docs/docs-zh.md?raw";

export function DocsPage() {
  const { t, i18n } = useTranslation();
  const [currentDoc, setCurrentDoc] = useState<string>("getting-started");

  // Get markdown content based on current language
  const markdownContent = useMemo(() => {
    return i18n.language.startsWith("zh") ? docsZh : docsEn;
  }, [i18n.language]);

  const containerStyles: React.CSSProperties = {
    display: "flex",
    gap: "1.5rem",
    height: "100%",
  };

  const sidebarWrapperStyles: React.CSSProperties = {
    flexShrink: 0,
  };

  const contentStyles: React.CSSProperties = {
    flex: 1,
    overflow: "auto",
    padding: "0.5rem",
  };

  return (
    <div
      style={{
        height: "100%",
        overflow: "hidden",
        padding: "1rem 1.5rem",
        boxSizing: "border-box",
      }}
    >
      <TitleCard title={t("pages.docsPage.documentation")} />

      <div style={containerStyles}>
        <div style={sidebarWrapperStyles}>
          <DocsSidebar currentDoc={currentDoc} onDocChange={setCurrentDoc} />
        </div>

        <div style={contentStyles}>
          <MarkdownRenderer content={markdownContent} />
        </div>
      </div>
    </div>
  );
}

export default DocsPage;
