/**
 * DocItem/Content Theme Swizzle (Wrap)
 *
 * Wraps the original DocItem/Content component with LessonContent
 * to provide tabbed interface for Full Lesson and AI Summary views.
 *
 * The summary is read from global data (populated by docusaurus-summaries-plugin)
 * which scans for .summary.md files at build time.
 */

import React, { useState, useEffect, useRef } from "react";
import Content from "@theme-original/DocItem/Content";
import type ContentType from "@theme/DocItem/Content";
import type { WrapperProps } from "@docusaurus/types";
import { useDoc } from "@docusaurus/plugin-content-docs/client";
import { usePluginData } from "@docusaurus/useGlobalData";
import LessonContent from "../../../components/LessonContent";
import ReactMarkdown from "react-markdown";
import ReadingProgress from "@/components/ReadingProgress";
import DocPageActions from "@/components/DocPageActions";
import { useStudyMode } from "@/contexts/StudyModeContext";
import { useAuth } from "@/contexts/AuthContext";
import { TeachMePanel } from '@/components/TeachMePanel';

type Props = WrapperProps<typeof ContentType>;

/**
 * Reading Time Component - calculates from content
 */
function ReadingTime() {
  const [readingTime, setReadingTime] = useState<number | null>(null);

  useEffect(() => {
    // Calculate reading time from article content
    const article = document.querySelector("article");
    if (article) {
      const text = article.textContent || "";
      const words = text.trim().split(/\s+/).length;
      const minutes = Math.ceil(words / 200); // 200 words per minute
      setReadingTime(minutes);
    }
  }, []);

  if (!readingTime) return null;

  return (
    <div className="reading-time">
      <svg
        width="14"
        height="14"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <circle cx="12" cy="12" r="10" />
        <polyline points="12 6 12 12 16 14" />
      </svg>
      <span>{readingTime} min read</span>
    </div>
  );
}

/**
 * Back to Top Button Component
 * Only shows when user scrolls UP (not always visible after scrolling down)
 */
function BackToTopButton() {
  const [visible, setVisible] = useState(false);
  const lastScrollY = useRef(0);

  useEffect(() => {
    const handleScroll = () => {
      const currentScrollY = window.scrollY;

      // Show only when:
      // 1. User has scrolled down at least 400px AND
      // 2. User is scrolling UP (current position < last position)
      const isScrollingUp = currentScrollY < lastScrollY.current;
      const hasScrolledEnough = currentScrollY > 400;

      setVisible(isScrollingUp && hasScrolledEnough);
      lastScrollY.current = currentScrollY;
    };

    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  const scrollToTop = () => {
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  if (!visible) return null;

  return (
    <button
      onClick={scrollToTop}
      className="back-to-top-button"
      title="Back to top"
      aria-label="Scroll back to top"
    >
      <svg
        width="20"
        height="20"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M18 15l-6-6-6 6" />
      </svg>
    </button>
  );
}

interface SummariesPluginData {
  summaries: Record<string, string>;
}

export default function ContentWrapper(props: Props): React.ReactElement {
  const doc = useDoc();

  // Persist zen mode in localStorage
  const [zenMode, setZenMode] = React.useState(() => {
    if (typeof window !== "undefined") {
      return localStorage.getItem("zenMode") === "true";
    }
    return false;
  });

  React.useEffect(() => {
    if (zenMode) {
      document.body.classList.add("zen-mode");
      localStorage.setItem("zenMode", "true");
    } else {
      document.body.classList.remove("zen-mode");
      localStorage.setItem("zenMode", "false");
    }
  }, [zenMode]);

  // Apply zen mode on mount (for SSR hydration)
  React.useEffect(() => {
    if (localStorage.getItem("zenMode") === "true") {
      document.body.classList.add("zen-mode");
    }
  }, []);

  // Get summaries from global data (populated by docusaurus-summaries-plugin)
  let summaries: Record<string, string> = {};
  try {
    const pluginData = usePluginData("docusaurus-summaries-plugin") as
      | SummariesPluginData
      | undefined;
    summaries = pluginData?.summaries || {};
  } catch {
    // Plugin might not be loaded yet or doesn't exist
    summaries = {};
  }

  // Get the doc's source path to look up its summary
  // The sourceDirName is like "01-Introducing-AI-Driven-Development/01-ai-development-revolution"
  // The slug is the doc ID
  // The summary key is stored as relative path without .summary.md
  // e.g., "01-Introducing-AI-Driven-Development/01-ai-development-revolution/08-traditional-cs-education-gaps"

  // Build the lookup key from doc metadata
  const metadata = doc.metadata;
  const sourceDirName = metadata.sourceDirName || "";
  const slug = metadata.slug || "";

  // The source path in doc metadata points to the markdown file
  // We need to construct the summary lookup key
  // Doc ID format example: "01-Introducing-AI-Driven-Development/01-ai-development-revolution/08-traditional-cs-education-gaps"
  const docId = metadata.id;

  // Debug log in development
  if (typeof window !== "undefined" && process.env.NODE_ENV === "development") {
    console.log("[DocItem/Content] Doc ID:", docId);
    console.log("[DocItem/Content] Source dir:", sourceDirName);
    console.log("[DocItem/Content] Slug:", slug);
    console.log(
      "[DocItem/Content] Available summaries:",
      Object.keys(summaries),
    );
  }

  // Look up summary by doc ID (the key format matches how plugin stores them)
  const summary = summaries[docId];

  // Get lesson path for TeachMePanel
  // Use metadata.source for the actual file path with numeric prefixes
  // Format: @site/docs/01-Part/02-Chapter/03-lesson.md -> 01-Part/02-Chapter/03-lesson
  const rawSource = (metadata as { source?: string }).source || "";
  const lessonPath = rawSource
    .replace(/^@site\/docs\//, "")
    .replace(/\.(md|mdx)$/, "");

  // Study mode controls
  const { isOpen: isStudyModeOpen, openPanel } = useStudyMode();
  const { session } = useAuth();
  const isLoggedIn = !!session?.user;

  // Determine if this is a content page vs category landing page
  // - Lessons have 3+ path segments: part/chapter/lesson
  // - Special root pages (thesis, preface) have 1 segment but ARE content pages
  // - Parts have 1 segment (category landing - no panel)
  // - Chapters have 2 segments (category landing - no panel)
  const pathSegments = docId.split("/").filter(Boolean);
  const specialRootPages = ["thesis", "preface"];
  const isSpecialRootPage = pathSegments.length === 1 && specialRootPages.includes(pathSegments[0]);
  const isLeafPage = pathSegments.length >= 3 || isSpecialRootPage;

  // If no summary, just render original content
  if (!summary) {
    return (
      <>
        <ReadingProgress />
        <div className="doc-content-header">
          <ReadingTime />
          <DocPageActions />
        </div>
        {/* Floating action buttons - hidden when study mode panel is open */}
        {!isStudyModeOpen && (
          <div className="floating-actions">
            <BackToTopButton />
            {/* Study Mode button - only for logged-in users on lesson pages */}
            {isLoggedIn && isLeafPage && (
              <button
                onClick={openPanel}
                className="study-mode-float"
                title="Study Mode"
                aria-label="Open Study Mode"
              >
                <svg
                  width="20"
                  height="20"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  {/* Graduation cap */}
                  <path d="M22 10v6M2 10l10-5 10 5-10 5z" />
                  <path d="M6 12v5c0 1.5 2.5 3 6 3s6-1.5 6-3v-5" />
                </svg>
              </button>
            )}
            <button
              onClick={() => setZenMode(!zenMode)}
              className="zen-mode-toggle"
              title={zenMode ? "Exit Focus Mode" : "Focus Mode"}
              aria-label={zenMode ? "Exit Focus Mode" : "Enter Focus Mode"}
            >
              {zenMode ? (
                // Exit: Grid/sidebar icon
                <svg
                  width="20"
                  height="20"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <rect x="3" y="3" width="7" height="7"></rect>
                  <rect x="14" y="3" width="7" height="7"></rect>
                  <rect x="14" y="14" width="7" height="7"></rect>
                  <rect x="3" y="14" width="7" height="7"></rect>
                </svg>
              ) : (
                // Enter: Focus/center icon
                <svg
                  width="20"
                  height="20"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <circle cx="12" cy="12" r="3"></circle>
                  <path d="M3 12h4m10 0h4M12 3v4m0 10v4"></path>
                </svg>
              )}
            </button>
          </div>
        )}
        <Content {...props} />
        {isLeafPage && <TeachMePanel lessonPath={lessonPath} />}
      </>
    );
  }

  // Render summary as markdown
  // Calculate reading time
  // Assuming 200 words per minute
  // We need to get the text content. Since we don't have direct access to the raw markdown here easily without parsing,
  // we can use a rough estimate based on the rendered content or just skip it if it's too complex to get right now.
  // Actually, Docusaurus usually provides reading time in metadata if configured, but let's check.
  // doc.metadata.readingTime is available if the readingTime option is enabled in preset.
  // Let's check if we can access it.

  // For now, let's just use the progress bar and zoom as the main features.
  // If we want reading time, we should enable it in docusaurus.config.ts first.

  const summaryElement = <ReactMarkdown>{summary}</ReactMarkdown>;

  return (
    <>
      <ReadingProgress />
      <div className="doc-content-header">
        <ReadingTime />
        <DocPageActions />
      </div>
      {/* Floating action buttons - hidden when study mode panel is open */}
      {!isStudyModeOpen && (
        <div className="floating-actions">
          <BackToTopButton />
          {/* Study Mode button - only for logged-in users on lesson pages */}
          {isLoggedIn && isLeafPage && (
            <button
              onClick={openPanel}
              className="study-mode-float"
              title="Study Mode"
              aria-label="Open Study Mode"
            >
              <svg
                width="20"
                height="20"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                {/* Graduation cap */}
                <path d="M22 10v6M2 10l10-5 10 5-10 5z" />
                <path d="M6 12v5c0 1.5 2.5 3 6 3s6-1.5 6-3v-5" />
              </svg>
            </button>
          )}
          <button
            onClick={() => setZenMode(!zenMode)}
            className="zen-mode-toggle"
            title={zenMode ? "Exit Focus Mode" : "Focus Mode"}
            aria-label={zenMode ? "Exit Focus Mode" : "Enter Focus Mode"}
          >
            {zenMode ? (
              // Exit: Grid/sidebar icon
              <svg
                width="20"
                height="20"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <rect x="3" y="3" width="7" height="7"></rect>
                <rect x="14" y="3" width="7" height="7"></rect>
                <rect x="14" y="14" width="7" height="7"></rect>
                <rect x="3" y="14" width="7" height="7"></rect>
              </svg>
            ) : (
              // Enter: Focus/center icon
              <svg
                width="20"
                height="20"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <circle cx="12" cy="12" r="3"></circle>
                <path d="M3 12h4m10 0h4M12 3v4m0 10v4"></path>
              </svg>
            )}
          </button>
        </div>
      )}
      <LessonContent summaryElement={summaryElement}>
        <Content {...props} />
        {/* TODO: ASK ME ENALBE AFTER BACKEND DEP */}
      </LessonContent>
      {isLeafPage && <TeachMePanel lessonPath={lessonPath} />}
    </>
  );
}
