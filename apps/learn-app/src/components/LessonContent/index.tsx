/**
 * LessonContent Component
 *
 * A refined tabbed interface for lesson content with Full Lesson and Summary views.
 * Implements "Scholarly Precision" aesthetic with Polar Night theme integration.
 *
 * The Summary tab only appears when summaryElement is provided.
 * Summary tab is locked for non-authenticated users.
 * Personalization tab allows AI-powered content adaptation.
 * Automatically wrapped around doc content via the DocItem/Content theme swizzle.
 */

import React, { useState, useRef, useCallback, useEffect } from "react";
import { useLocation } from "@docusaurus/router";
import ReactMarkdown from "react-markdown";
import { useAuth } from "@/contexts/AuthContext";
import { usePersonalization } from "@/hooks/usePersonalization";
import ContentGate from "@/components/ContentGate";
import styles from "./styles.module.css";

interface LessonContentProps {
  children: React.ReactNode;
  summaryElement?: React.ReactNode;
  /** Raw markdown content for personalization (passed from MDX) */
  rawContent?: string;
}

/**
 * Document Icon - Represents full lesson content
 */
const DocumentIcon: React.FC<{ className?: string }> = ({ className }) => (
  <svg
    className={className}
    width="18"
    height="18"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden="true"
  >
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
    <polyline points="14,2 14,8 20,8" />
    <line x1="16" y1="13" x2="8" y2="13" />
    <line x1="16" y1="17" x2="8" y2="17" />
    <line x1="10" y1="9" x2="8" y2="9" />
  </svg>
);

/**
 * Summary Icon - Represents condensed summary content
 */
const SummaryIcon: React.FC<{ className?: string }> = ({ className }) => (
  <svg
    className={className}
    width="18"
    height="18"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden="true"
  >
    <line x1="21" y1="10" x2="3" y2="10" />
    <line x1="21" y1="6" x2="3" y2="6" />
    <line x1="21" y1="14" x2="3" y2="14" />
    <line x1="21" y1="18" x2="3" y2="18" />
  </svg>
);

/**
 * Lock Icon - Shows when content is locked
 */
const LockIcon: React.FC<{ className?: string }> = ({ className }) => (
  <svg
    className={className}
    width="14"
    height="14"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden="true"
  >
    <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
    <path d="M7 11V7a5 5 0 0 1 10 0v4" />
  </svg>
);

/**
 * Personalization Icon - Represents personalized content
 */
const PersonalizationIcon: React.FC<{ className?: string }> = ({
  className,
}) => (
  <svg
    className={className}
    width="18"
    height="18"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden="true"
  >
    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
    <circle cx="12" cy="7" r="4" />
  </svg>
);

type TabType = "lesson" | "summary" | "personalization";

/**
 * Sparkle Icon - Indicates AI-generated content
 */
const SparkleIcon: React.FC<{ className?: string }> = ({ className }) => (
  <svg
    className={className}
    width="18"
    height="18"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden="true"
  >
    <path d="M12 3l1.5 5.5L19 10l-5.5 1.5L12 17l-1.5-5.5L5 10l5.5-1.5L12 3z" />
    <path d="M5 3l.5 2L3 5.5l2 .5.5 2 .5-2 2-.5-2-.5L5 3z" />
    <path d="M19 17l.5 2-2 .5 2 .5.5 2 .5-2 2-.5-2-.5-.5-2z" />
  </svg>
);

/**
 * PersonalizationPanel Component
 *
 * Handles the AI personalization workflow:
 * 1. Auto-generates when mounted (tab selected)
 * 2. Streams content in real-time as it generates
 * 3. Shows error state with retry option
 * 4. Caches results for instant replay
 */
const PersonalizationPanel: React.FC<{
  lessonId: string;
  rawContent?: string;
  isActive: boolean;
}> = ({ lessonId, rawContent, isActive }) => {
  const { personalize, result, streamingContent, loading, error, reset } =
    usePersonalization();
  const hasStartedRef = useRef(false);

  // Auto-generate when tab becomes active
  useEffect(() => {
    if (isActive && !hasStartedRef.current && !result && !loading && !error) {
      hasStartedRef.current = true;

      // Use a fallback if raw content not provided
      const contentToPersonalize =
        rawContent ||
        "This lesson content is being personalized. The original content will be adapted to your learning preferences.";

      personalize(lessonId, contentToPersonalize);
    }
  }, [isActive, lessonId, rawContent, result, loading, error, personalize]);

  // Reset the started flag when reset is called
  const handleReset = useCallback(() => {
    hasStartedRef.current = false;
    reset();
  }, [reset]);

  const handleRetry = useCallback(() => {
    hasStartedRef.current = false;
    const contentToPersonalize =
      rawContent ||
      "This lesson content is being personalized. The original content will be adapted to your learning preferences.";
    personalize(lessonId, contentToPersonalize);
  }, [lessonId, rawContent, personalize]);

  // Loading state with streaming content
  if (loading) {
    return (
      <div className={styles.personalizedResult}>
        <div className={styles.resultHeader}>
          <div className={styles.resultBadge}>
            <SparkleIcon />
            <span>Generating...</span>
          </div>
          <div className={styles.streamingIndicator}>
            <div className={styles.loadingDots}>
              <span></span>
              <span></span>
              <span></span>
            </div>
          </div>
        </div>

        {streamingContent ? (
          <div className={styles.personalizedContent}>
            <ReactMarkdown>{streamingContent}</ReactMarkdown>
            <span className={styles.streamingCursor}>▊</span>
          </div>
        ) : (
          <div className={styles.loadingState}>
            <div className={styles.loadingSpinner} />
            <p>Connecting to AI...</p>
          </div>
        )}
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className={styles.errorState}>
        <p className={styles.errorMessage}>{error}</p>
        <div className={styles.errorActions}>
          <button className={styles.retryButton} onClick={handleRetry}>
            Try Again
          </button>
          <button className={styles.resetButton} onClick={handleReset}>
            Cancel
          </button>
        </div>
      </div>
    );
  }

  // Success state - show personalized content
  if (result) {
    return (
      <div className={styles.personalizedResult}>
        <div className={styles.resultHeader}>
          <div className={styles.resultBadge}>
            <SparkleIcon />
            <span>AI Personalized</span>
          </div>
          <span className={styles.resultMeta}>
            {result.cached ? "From cache • Instant" : "Freshly generated"} •{" "}
            {result.selectedInterest}
          </span>
        </div>

        {result.analogyLogic && (
          <div className={styles.analogyBox}>
            <strong>Adaptation approach:</strong>
            <p>{result.analogyLogic}</p>
          </div>
        )}

        <div className={styles.personalizedContent}>
          <ReactMarkdown>{result.personalizedContent}</ReactMarkdown>
        </div>

        <div className={styles.resultFooter}>
          <button className={styles.regenerateButton} onClick={handleRetry}>
            <SparkleIcon />
            Regenerate
          </button>
          <button className={styles.resetButton} onClick={handleReset}>
            Clear
          </button>
        </div>
      </div>
    );
  }

  // Initial state (shouldn't show for long - auto-generates)
  return (
    <div className={styles.loadingState}>
      <div className={styles.loadingSpinner} />
      <p>Starting personalization...</p>
    </div>
  );
};

export const LessonContent: React.FC<LessonContentProps> = ({
  children,
  summaryElement,
  rawContent,
}) => {
  const [activeTab, setActiveTab] = useState<TabType>("lesson");
  const contentRef = useRef<HTMLDivElement>(null);
  const { session, isLoading } = useAuth();
  const location = useLocation();

  // Extract lesson ID from URL path
  // e.g., /01-General-Agents-Foundations/01-agent-factory-paradigm/01-intro
  const lessonId = location.pathname.replace(/^\//, "").replace(/\/$/, "");

  // Check if user is authenticated
  const isAuthenticated = !!session && !isLoading;

  // Read initial tab from URL hash on mount
  useEffect(() => {
    const hash = window.location.hash.replace("#", "") as TabType;
    if (hash === "summary" || hash === "personalization") {
      setActiveTab(hash);
    }
  }, []);

  // If no summary available, just render children without tabs
  if (!summaryElement) {
    return <>{children}</>;
  }

  const handleTabChange = useCallback((tab: TabType) => {
    setActiveTab(tab);
    // Update URL hash (lesson tab = no hash, others = #tabname)
    if (tab === "lesson") {
      window.history.replaceState(
        null,
        "",
        window.location.pathname + window.location.search,
      );
    } else {
      window.history.replaceState(
        null,
        "",
        window.location.pathname + window.location.search + "#" + tab,
      );
    }
    // Smooth scroll to top of content when switching tabs
    contentRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, []);

  return (
    <div className={styles.lessonContent} ref={contentRef}>
      {/* Tab Navigation */}
      <nav className={styles.tabNav} role="tablist" aria-label="Content view">
        <button
          role="tab"
          aria-selected={activeTab === "lesson"}
          aria-controls="panel-lesson"
          id="tab-lesson"
          tabIndex={activeTab === "lesson" ? 0 : -1}
          className={`${styles.tab} ${activeTab === "lesson" ? styles.tabActive : ""}`}
          onClick={() => handleTabChange("lesson")}
          onKeyDown={(e: React.KeyboardEvent) => {
            if (e.key === "ArrowRight") {
              handleTabChange("summary");
              document.getElementById("tab-summary")?.focus();
            }
          }}
        >
          <span className={styles.tabIcon}>
            <DocumentIcon />
          </span>
          <span className={styles.tabLabel}>Full Lesson</span>
        </button>

        <button
          role="tab"
          aria-selected={activeTab === "summary"}
          aria-controls="panel-summary"
          id="tab-summary"
          tabIndex={activeTab === "summary" ? 0 : -1}
          className={`${styles.tab} ${activeTab === "summary" ? styles.tabActive : ""} ${!isAuthenticated ? styles.tabLocked : ""}`}
          onClick={() => handleTabChange("summary")}
          onKeyDown={(e: React.KeyboardEvent) => {
            if (e.key === "ArrowLeft") {
              handleTabChange("lesson");
              document.getElementById("tab-lesson")?.focus();
            }
            if (e.key === "ArrowRight") {
              handleTabChange("personalization");
              document.getElementById("tab-personalization")?.focus();
            }
          }}
        >
          <span className={styles.tabIcon}>
            <SummaryIcon />
          </span>
          <span className={styles.tabLabel}>Summary</span>
          {!isAuthenticated && (
            <span className={styles.tabLockIcon} title="Sign in to unlock">
              <LockIcon />
            </span>
          )}
        </button>

        <button
          role="tab"
          aria-selected={activeTab === "personalization"}
          aria-controls="panel-personalization"
          id="tab-personalization"
          tabIndex={activeTab === "personalization" ? 0 : -1}
          className={`${styles.tab} ${activeTab === "personalization" ? styles.tabActive : ""} ${!isAuthenticated ? styles.tabLocked : ""}`}
          onClick={() => handleTabChange("personalization")}
          onKeyDown={(e: React.KeyboardEvent) => {
            if (e.key === "ArrowLeft") {
              handleTabChange("summary");
              document.getElementById("tab-summary")?.focus();
            }
          }}
        >
          <span className={styles.tabIcon}>
            <PersonalizationIcon />
          </span>
          <span className={styles.tabLabel}>Personalization</span>
          {!isAuthenticated && (
            <span className={styles.tabLockIcon} title="Sign in to unlock">
              <LockIcon />
            </span>
          )}
        </button>
      </nav>

      {/* Content Panels */}
      <div className={styles.panelContainer}>
        {/* Full Lesson Panel */}
        <div
          role="tabpanel"
          id="panel-lesson"
          aria-labelledby="tab-lesson"
          className={`${styles.panel} ${activeTab === "lesson" ? styles.panelActive : ""}`}
          hidden={activeTab !== "lesson"}
        >
          {children}
        </div>

        {/* Summary Panel */}
        <div
          role="tabpanel"
          id="panel-summary"
          aria-labelledby="tab-summary"
          className={`${styles.panel} ${activeTab === "summary" ? styles.panelActive : ""}`}
          hidden={activeTab !== "summary"}
        >
          {isAuthenticated ? (
            <div className={styles.summaryContent}>
              <div className={styles.summaryBody}>{summaryElement}</div>
            </div>
          ) : (
            <ContentGate type="summary">
              <div className={styles.summaryContent}>
                <div className={styles.summaryBody}>{summaryElement}</div>
              </div>
            </ContentGate>
          )}
        </div>

        {/* Personalization Panel */}
        <div
          role="tabpanel"
          id="panel-personalization"
          aria-labelledby="tab-personalization"
          className={`${styles.panel} ${activeTab === "personalization" ? styles.panelActive : ""}`}
          hidden={activeTab !== "personalization"}
        >
          {isAuthenticated ? (
            <div className={styles.summaryContent}>
              <div className={styles.summaryBody}>
                <PersonalizationPanel
                  lessonId={lessonId}
                  rawContent={rawContent}
                  isActive={activeTab === "personalization"}
                />
              </div>
            </div>
          ) : (
            <ContentGate type="personalization">
              <div className={styles.summaryContent}>
                <div className={styles.summaryBody}>
                  <PersonalizationPanel
                    lessonId={lessonId}
                    rawContent={rawContent}
                    isActive={activeTab === "personalization"}
                  />
                </div>
              </div>
            </ContentGate>
          )}
        </div>
      </div>
    </div>
  );
};

export default LessonContent;
