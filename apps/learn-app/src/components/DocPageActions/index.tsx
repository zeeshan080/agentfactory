/**
 * DocPageActions Component - Premium UX Edition
 *
 * Primary action: Copy Markdown (for AI assistance and documentation)
 * Secondary actions: Download Markdown, Ask ChatGPT, Ask Claude, Share
 *
 * Features:
 * - Client-side HTML-to-Markdown via Turndown (no API calls, offline-ready)
 * - Smooth icon morphing animations
 * - Keyboard shortcuts (Ctrl/Cmd+Shift+C to copy)
 * - Tooltips with action descriptions
 * - Full accessibility (ARIA, keyboard nav, focus states)
 * - Responsive design (collapses on mobile)
 */

import React, { useEffect, useCallback, useState } from "react";
import { useDoc } from "@docusaurus/plugin-content-docs/client";
import { usePluginData } from "@docusaurus/useGlobalData";
import useDocusaurusContext from "@docusaurus/useDocusaurusContext";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { siClaude } from "simple-icons/icons";
import TurndownService from "turndown";
import { useAuth } from "@/contexts/AuthContext";
import { getOAuthAuthorizationUrl } from "@/lib/auth-client";
import { useStudyMode } from "@/contexts/StudyModeContext";

// Concurrency limit for parallel fetching
const FETCH_CONCURRENCY = 4;

// ============================================================================
// ICONS - Optimized for animations
// ============================================================================

const CopyIcon = ({ className = "" }: { className?: string }) => (
  <svg
    className={`doc-actions-icon ${className}`}
    width="16"
    height="16"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden="true"
  >
    <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
    <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
  </svg>
);

const CheckIcon = ({ className = "" }: { className?: string }) => (
  <svg
    className={`doc-actions-icon doc-actions-icon--success ${className}`}
    width="16"
    height="16"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2.5"
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden="true"
  >
    <polyline points="20 6 9 17 4 12" />
  </svg>
);

const DownloadIcon = () => (
  <svg
    className="doc-actions-icon"
    width="16"
    height="16"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden="true"
  >
    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
    <polyline points="7 10 12 15 17 10" />
    <line x1="12" y1="15" x2="12" y2="3" />
  </svg>
);

const ChatGPTIcon = () => (
  <svg
    className="doc-actions-icon"
    width="16"
    height="16"
    viewBox="0 0 24 24"
    fill="currentColor"
    aria-hidden="true"
  >
    <path d="M22.282 9.821a5.985 5.985 0 0 0-.516-4.91 6.046 6.046 0 0 0-6.51-2.9A6.065 6.065 0 0 0 4.981 4.18a5.985 5.985 0 0 0-3.998 2.9 6.046 6.046 0 0 0 .743 7.097 5.98 5.98 0 0 0 .51 4.911 6.051 6.051 0 0 0 6.515 2.9A5.985 5.985 0 0 0 13.26 24a6.056 6.056 0 0 0 5.772-4.206 5.99 5.99 0 0 0 3.997-2.9 6.056 6.056 0 0 0-.747-7.073zM13.26 22.43a4.476 4.476 0 0 1-2.876-1.04l.141-.081 4.779-2.758a.795.795 0 0 0 .392-.681v-6.737l2.02 1.168a.071.071 0 0 1 .038.052v5.583a4.504 4.504 0 0 1-4.494 4.494zM3.6 18.304a4.47 4.47 0 0 1-.535-3.014l.142.085 4.783 2.759a.771.771 0 0 0 .78 0l5.843-3.369v2.332a.08.08 0 0 1-.033.062L9.74 19.95a4.5 4.5 0 0 1-6.14-1.646zM2.34 7.896a4.485 4.485 0 0 1 2.366-1.973V11.6a.766.766 0 0 0 .388.676l5.815 3.355-2.02 1.168a.076.076 0 0 1-.071 0l-4.83-2.786A4.504 4.504 0 0 1 2.34 7.872zm16.597 3.855l-5.833-3.387L15.119 7.2a.076.076 0 0 1 .071 0l4.83 2.791a4.494 4.494 0 0 1-.676 8.105v-5.678a.79.79 0 0 0-.407-.667zm2.01-3.023l-.141-.085-4.774-2.782a.776.776 0 0 0-.785 0L9.409 9.23V6.897a.066.066 0 0 1 .028-.061l4.83-2.787a4.5 4.5 0 0 1 6.68 4.66zm-12.64 4.135l-2.02-1.164a.08.08 0 0 1-.038-.057V6.075a4.5 4.5 0 0 1 7.375-3.453l-.142.08L8.704 5.46a.795.795 0 0 0-.393.681zm1.097-2.365l2.602-1.5 2.607 1.5v2.999l-2.597 1.5-2.607-1.5z" />
  </svg>
);

const ClaudeIcon = () => (
  <svg
    className="doc-actions-icon"
    width="16"
    height="16"
    viewBox="0 0 24 24"
    fill="currentColor"
    aria-hidden="true"
  >
    <path d={siClaude.path} />
  </svg>
);

const ChevronDownIcon = () => (
  <svg
    className="doc-actions-icon doc-actions-chevron-icon"
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
    <polyline points="6 9 12 15 18 9" />
  </svg>
);

const ShareIcon = () => (
  <svg
    className="doc-actions-icon"
    width="16"
    height="16"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden="true"
  >
    <circle cx="18" cy="5" r="3" />
    <circle cx="6" cy="12" r="3" />
    <circle cx="18" cy="19" r="3" />
    <line x1="8.59" y1="13.51" x2="15.42" y2="17.49" />
    <line x1="15.41" y1="6.51" x2="8.59" y2="10.49" />
  </svg>
);

const BookIcon = () => (
  <svg
    className="doc-actions-icon"
    width="16"
    height="16"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden="true"
  >
    <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
    <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
  </svg>
);

const LockIcon = () => (
  <svg
    className="doc-actions-icon doc-actions-icon--muted"
    width="12"
    height="12"
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

const LoadingIcon = () => (
  <svg
    className="doc-actions-icon doc-actions-icon--spin"
    width="16"
    height="16"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden="true"
  >
    <path d="M21 12a9 9 0 1 1-6.219-8.56" />
  </svg>
);

const TeachMeIcon = () => (
const StudyModeIcon = () => (
  <svg
    className="doc-actions-icon"
    width="16"
    height="16"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden="true"
  >
    <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z" />
    <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z" />
    {/* Graduation cap - symbolizes learning/study */}
    <path d="M22 10v6M2 10l10-5 10 5-10 5z" />
    <path d="M6 12v5c0 1.5 2.5 3 6 3s6-1.5 6-3v-5" />
    {/* Small sparkle - AI element */}
    <circle cx="20" cy="6" r="1.5" fill="currentColor" stroke="none" />
  </svg>
);

// ============================================================================
// TYPES
// ============================================================================

interface ChapterLesson {
  id: string;
  normalizedId: string;
  title: string;
  slug: string;
  order: number;
}

interface Chapter {
  title: string;
  part: string;
  partPath: string;
  chapterPath: string;
  lessons: ChapterLesson[];
}

interface ChapterManifestData {
  chapters: Record<string, Chapter>;
  docToChapter: Record<string, string>;
}

// ============================================================================
// TURNDOWN SERVICE - Markdown extraction
// ============================================================================

const turndownService = new TurndownService({
  headingStyle: "atx",
  codeBlockStyle: "fenced",
  bulletListMarker: "-",
  emDelimiter: "*",
  strongDelimiter: "**",
});

// Custom rule to preserve code blocks with language hints
turndownService.addRule("codeBlock", {
  filter: (node) => {
    return node.nodeName === "PRE" && node.querySelector("code") !== null;
  },
  replacement: (content, node) => {
    const codeElement = (node as HTMLElement).querySelector("code");
    if (!codeElement) return content;

    const className = codeElement.className || "";
    const langMatch = className.match(/language-(\w+)/);
    const lang = langMatch ? langMatch[1] : "";
    const code = codeElement.textContent || "";
    return `\n\`\`\`${lang}\n${code}\n\`\`\`\n`;
  },
});

// ============================================================================
// TOOLTIP COMPONENT - Simple hover tooltip
// ============================================================================

interface TooltipProps {
  content: string;
  shortcut?: string;
  children: React.ReactNode;
  position?: "top" | "bottom";
}

const Tooltip = ({
  content,
  shortcut,
  children,
  position = "bottom",
}: TooltipProps) => (
  <div className="doc-actions-tooltip-wrapper">
    {children}
    <div
      className={`doc-actions-tooltip doc-actions-tooltip--${position}`}
      role="tooltip"
    >
      <span>{content}</span>
      {shortcut && <kbd className="doc-actions-shortcut">{shortcut}</kbd>}
    </div>
  </div>
);

// ============================================================================
// MAIN COMPONENT
// ============================================================================

export function DocPageActions() {
  const doc = useDoc();
  const { siteConfig } = useDocusaurusContext();
  const { session, isLoading: authLoading } = useAuth();
  const { openPanel } = useStudyMode();
  const [copied, setCopied] = useState(false);
  const [downloaded, setDownloaded] = useState(false);
  const [chapterDownloading, setChapterDownloading] = useState(false);
  const [chapterDownloaded, setChapterDownloaded] = useState(false);
  const [downloadProgress, setDownloadProgress] = useState("");

  // Auth config from site config
  const authUrl = siteConfig.customFields?.authUrl as string | undefined;
  const oauthClientId = siteConfig.customFields?.oauthClientId as
    | string
    | undefined;

  // Get chapter manifest from global data
  let chapterManifest: ChapterManifestData | null = null;
  try {
    chapterManifest = usePluginData(
      "docusaurus-chapter-manifest-plugin",
    ) as ChapterManifestData;
  } catch {
    // Plugin might not be loaded
  }

  // Find current chapter info
  const docId = doc.metadata.id;
  const chapterKey = chapterManifest?.docToChapter?.[docId];
  const currentChapter = chapterKey
    ? chapterManifest?.chapters?.[chapterKey]
    : null;

  // Determine if this is a content page (lesson) vs category landing page
  // - Lessons: actual content files (NOT README.md)
  // - Parts: category landing (README.md in part folder) - no button
  // - Chapters: category landing (README.md in chapter folder) - no button
  // - Special root pages (thesis, preface) ARE content pages
  const pathSegments = docId.split("/").filter(Boolean);
  const lastSegment = pathSegments[pathSegments.length - 1] || "";

  // README files are category landing pages, not lessons
  const isReadmePage = lastSegment.toLowerCase() === "readme";

  // Special root pages that should show the button
  const specialRootPages = ["thesis", "preface-agent-native"];
  const isSpecialRootPage =
    pathSegments.length === 1 && specialRootPages.includes(pathSegments[0]);

  // A lesson page is:
  // - 3+ segments AND not a README (e.g., part/chapter/lesson)
  // - OR a special root page (thesis, preface)
  const isLessonPage =
    (pathSegments.length >= 3 && !isReadmePage) || isSpecialRootPage;

  // Detect platform for keyboard shortcut display
  const isMac =
    typeof navigator !== "undefined" &&
    /Mac|iPod|iPhone|iPad/.test(navigator.userAgent);
  const modKey = isMac ? "⌘" : "Ctrl";

  // Check if user is logged in
  // DEV BYPASS: Allow chapter download on localhost for testing
  const isDev =
    typeof window !== "undefined" && window.location.hostname === "localhost";
  const isLoggedIn = isDev || (!authLoading && session?.user);
  const isLoggedIn = !authLoading && session?.user;

  /**
   * Redirect to login page with return URL
   */
  const handleLoginRedirect = useCallback(async () => {
    try {
      // Include hash to preserve tab state (e.g., #summary, #personalization)
      const returnUrl =
        window.location.pathname +
        window.location.search +
        window.location.hash;
      const loginUrl = await getOAuthAuthorizationUrl(
        "signin",
        { authUrl, clientId: oauthClientId },
        returnUrl,
      );
      const returnUrl = window.location.href;
      // Store return URL for after login
      localStorage.setItem("auth_return_url", returnUrl);
      const loginUrl = await getOAuthAuthorizationUrl(undefined, {
        authUrl,
        clientId: oauthClientId,
      });
      window.location.href = loginUrl;
    } catch (err) {
      console.error("Failed to redirect to login:", err);
    }
  }, [authUrl, oauthClientId]);

  /**
   * Extract markdown from the rendered page content.
   * Uses Turndown to convert HTML to Markdown client-side.
   * No external API calls - works offline with zero rate limiting.
   */
  const extractMarkdown = useCallback((): string => {
    const article = document.querySelector("article");
    if (!article) {
      return `# ${doc.metadata.title}\n\n${window.location.href}`;
    }

    const clone = article.cloneNode(true) as HTMLElement;

    // Remove UI elements we don't want in the markdown
    const selectorsToRemove = [
      ".theme-doc-footer",
      ".pagination-nav",
      ".doc-content-header",
      ".floating-actions",
      ".theme-code-block-copied-btn",
      ".docSidebarContainer",
      ".tocCollapsible",
      "button",
      ".admonition-icon",
      ".hash-link",
    ];

    selectorsToRemove.forEach((selector) => {
      clone.querySelectorAll(selector).forEach((el) => el.remove());
    });

    const hasH1 = clone.querySelector("h1");
    let markdown = "";

    if (!hasH1 && doc.metadata.title) {
      markdown = `# ${doc.metadata.title}\n\n`;
    }

    markdown += turndownService.turndown(clone.innerHTML);
    markdown += `\n\n---\nSource: ${window.location.href}`;

    return markdown;
  }, [doc.metadata.title]);

  // Copy markdown to clipboard
  const handleCopyMarkdown = useCallback(async () => {
    try {
      const markdown = extractMarkdown();
      await navigator.clipboard.writeText(markdown);
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    } catch (err) {
      console.error("Failed to copy:", err);
      // Fallback: copy the page URL
      try {
        await navigator.clipboard.writeText(window.location.href);
        setCopied(true);
        setTimeout(() => setCopied(false), 2500);
      } catch {
        // Silent fail - clipboard might not be available
      }
    }
  }, [extractMarkdown]);

  // Download markdown file
  const handleDownloadMarkdown = useCallback(() => {
    try {
      const markdown = extractMarkdown();
      const title =
        doc.metadata.title || doc.metadata.id.split("/").pop() || "document";
      const filename = `${title.replace(/[^a-zA-Z0-9-_ ]/g, "")}.md`;

      const blob = new Blob([markdown], { type: "text/markdown" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);

      setDownloaded(true);
      setTimeout(() => setDownloaded(false), 2500);
    } catch (err) {
      console.error("Failed to download:", err);
    }
  }, [extractMarkdown, doc.metadata.title, doc.metadata.id]);

  // Open in ChatGPT
  const handleOpenInChatGPT = useCallback(() => {
    const prompt = `Read from ${window.location.href} so I can ask questions about it.`;
    const chatGptUrl = `https://chat.openai.com/?hints=search&q=${encodeURIComponent(prompt)}`;
    window.open(chatGptUrl, "_blank", "noopener,noreferrer");
  }, []);

  // Open in Claude
  const handleOpenInClaude = useCallback(() => {
    const prompt = `Read from ${window.location.href} so I can ask questions about it.`;
    const claudeUrl = `https://claude.ai/new?q=${encodeURIComponent(prompt)}`;
    window.open(claudeUrl, "_blank", "noopener,noreferrer");
  }, []);

  // Share functionality
  const handleShare = useCallback(async () => {
    if (navigator.share) {
      try {
        await navigator.share({
          title: doc.metadata.title,
          url: window.location.href,
        });
      } catch {
        // User cancelled or error - silent fail
      }
    } else {
      // Fallback: copy link
      try {
        await navigator.clipboard.writeText(window.location.href);
        setCopied(true);
        setTimeout(() => setCopied(false), 2500);
      } catch {
        // Silent fail
      }
    }
  }, [doc.metadata.title]);

  /**
   * Extract markdown from a URL by fetching the page and converting HTML to Markdown.
   */
  const extractMarkdownFromUrl = useCallback(
    async (url: string, title: string): Promise<string> => {
      try {
        const response = await fetch(url);
        if (!response.ok) {
          throw new Error(`Failed to fetch ${url}`);
        }
        const html = await response.text();

        // Parse HTML and extract article content
        const parser = new DOMParser();
        const doc = parser.parseFromString(html, "text/html");
        const article = doc.querySelector("article");

        if (!article) {
          return `# ${title}\n\n*Content could not be extracted*\n\nSource: ${url}`;
        }

        const clone = article.cloneNode(true) as HTMLElement;

        // Remove UI elements
        const selectorsToRemove = [
          ".theme-doc-footer",
          ".pagination-nav",
          ".doc-content-header",
          ".floating-actions",
          ".theme-code-block-copied-btn",
          ".docSidebarContainer",
          ".tocCollapsible",
          "button",
          ".admonition-icon",
          ".hash-link",
        ];

        selectorsToRemove.forEach((selector) => {
          clone.querySelectorAll(selector).forEach((el) => el.remove());
        });

        // Check if there's already an H1
        const hasH1 = clone.querySelector("h1");
        let markdown = "";

        if (!hasH1 && title) {
          markdown = `# ${title}\n\n`;
        }

        markdown += turndownService.turndown(clone.innerHTML);
        markdown += `\n\n---\nSource: ${url}`;

        return markdown;
      } catch (err) {
        console.error(`Failed to extract markdown from ${url}:`, err);
        return `# ${title}\n\n*Content could not be extracted*\n\nSource: ${url}`;
      }
    },
    [],
  );

  /**
   * Parallel fetch with concurrency limit
   */
  const fetchWithConcurrency = useCallback(
    async <T,>(
      items: T[],
      fetcher: (
        item: T,
        index: number,
      ) => Promise<{ index: number; result: string }>,
      onProgress: (completed: number, current: string) => void,
    ): Promise<Map<number, string>> => {
      const results = new Map<number, string>();
      let completedCount = 0;

      // Process in batches
      for (let i = 0; i < items.length; i += FETCH_CONCURRENCY) {
        const batch = items.slice(i, i + FETCH_CONCURRENCY);
        const batchPromises = batch.map((item, batchIndex) =>
          fetcher(item, i + batchIndex),
        );

        const batchResults = await Promise.all(batchPromises);

        for (const { index, result } of batchResults) {
          results.set(index, result);
          completedCount++;
          const item = items[index] as ChapterLesson;
          onProgress(completedCount, item.title);
        }
      }

      return results;
    },
    [],
  );

  /**
   * Download entire chapter as a single consolidated Markdown file.
   * All lessons are concatenated with a table of contents.
   * Only available for logged-in users.
   */
  const handleDownloadChapter = useCallback(async () => {
    if (!currentChapter) return;

    // If not logged in, redirect to login
    if (!isLoggedIn) {
      await handleLoginRedirect();
      return;
    }

    setChapterDownloading(true);
    setDownloadProgress("Preparing...");

    try {
      const baseUrl = window.location.origin;

      // Fetch all lessons in parallel with concurrency limit
      const lessonResults = await fetchWithConcurrency(
        currentChapter.lessons,
        async (lesson, index) => {
          const lessonUrl = `${baseUrl}${lesson.slug}`;
          const markdown = await extractMarkdownFromUrl(
            lessonUrl,
            lesson.title,
          );
          return { index, result: markdown };
        },
        (completed, currentTitle) => {
          setDownloadProgress(
            `${currentTitle} (${completed}/${currentChapter.lessons.length})`,
          );
        },
      );

      setDownloadProgress("Building document...");

      // Generate anchor ID from lesson title
      const toAnchor = (title: string): string => {
        return title
          .toLowerCase()
          .replace(/[^a-z0-9\s-]/g, "")
          .replace(/\s+/g, "-");
      };

      // Build table of contents
      const toc = currentChapter.lessons
        .map(
          (lesson, i) =>
            `${i + 1}. [${lesson.title}](#${toAnchor(lesson.title)})`,
        )
        .join("\n");

      // Build consolidated markdown
      const sections: string[] = [
        `# ${currentChapter.part}: ${currentChapter.title}`,
        "",
        `> Downloaded from Agent Factory on ${new Date().toLocaleDateString()}`,
        `> Total lessons: ${currentChapter.lessons.length}`,
        "",
        "## Table of Contents",
        "",
        toc,
        "",
        "---",
        "",
      ];

      // Add each lesson's content
      for (const lesson of currentChapter.lessons) {
        const index = currentChapter.lessons.indexOf(lesson);
        let markdown =
          lessonResults.get(index) ||
          `# ${lesson.title}\n\n*Content could not be extracted*`;

        // Remove the "Source:" footer from individual lessons (we'll add one at the end)
        markdown = markdown.replace(/\n\n---\nSource:.*$/, "");

        sections.push(markdown);
        sections.push("");
        sections.push("---");
        sections.push("");
      }

      // Add final source attribution
      sections.push(
        `Source: ${window.location.origin}/docs/${currentChapter.partPath}/${currentChapter.chapterPath}`,
      );

      const consolidatedMarkdown = sections.join("\n");

      // Download as single MD file
      const chapterFileName = currentChapter.title.replace(
        /[^a-zA-Z0-9-_ ]/g,
        "",
      );
      const blob = new Blob([consolidatedMarkdown], { type: "text/markdown" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${chapterFileName}.md`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);

      setChapterDownloaded(true);
      setTimeout(() => setChapterDownloaded(false), 3000);
    } catch (err) {
      console.error("Failed to download chapter:", err);
      setDownloadProgress("Download failed");
      setTimeout(() => setDownloadProgress(""), 2000);
    } finally {
      setChapterDownloading(false);
      if (!downloadProgress.includes("failed")) {
        setDownloadProgress("");
      }
    }
  }, [
    currentChapter,
    isLoggedIn,
    handleLoginRedirect,
    extractMarkdownFromUrl,
    fetchWithConcurrency,
    downloadProgress,
  ]);

  // Keyboard shortcut handler
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Ctrl/Cmd + Shift + C to copy markdown
      if (
        (e.ctrlKey || e.metaKey) &&
        e.shiftKey &&
        e.key.toLowerCase() === "c"
      ) {
        e.preventDefault();
        handleCopyMarkdown();
      }
      // Ctrl/Cmd + Shift + D to download
      if (
        (e.ctrlKey || e.metaKey) &&
        e.shiftKey &&
        e.key.toLowerCase() === "d"
      ) {
        e.preventDefault();
        handleDownloadMarkdown();
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [handleCopyMarkdown, handleDownloadMarkdown]);

  return (
    <div className="doc-page-actions" role="toolbar" aria-label="Page actions">
      {/* Teach Me Button - temporarily disabled */}
      {/* <Tooltip content="AI Study Mode" position="bottom">
                <button
                    className="doc-page-actions-teach-me"
                    onClick={openPanel}
                    aria-label="Open AI Study Mode"
                >
                    <TeachMeIcon />
                    <span>Teach Me</span>
                </button>
            </Tooltip> */}
      {/* Study Mode Button - Only shown on lesson pages for logged-in users */}
      {isLessonPage && isLoggedIn && (
        <Tooltip content="AI-powered Socratic learning" position="bottom">
          <button
            className="doc-page-actions-study-mode"
            onClick={openPanel}
            aria-label="Open Study Mode"
          >
            <StudyModeIcon />
            <span>Study Mode</span>
          </button>
        </Tooltip>
      )}

      {/* Split Button: Main action + Dropdown trigger */}
      <div
        className={`doc-page-actions-split ${copied ? "doc-page-actions-split--success" : ""}`}
      >
        {/* Primary Action: Copy Markdown */}
        <Tooltip
          content={copied ? "Copied!" : "Copy as Markdown"}
          shortcut={copied ? undefined : `${modKey}+⇧+C`}
          position="bottom"
        >
          <button
            className={`doc-page-actions-main ${copied ? "doc-page-actions-main--success" : ""}`}
            onClick={handleCopyMarkdown}
            aria-label={
              copied ? "Copied to clipboard" : "Copy page as Markdown"
            }
            aria-pressed={copied}
          >
            <span className="doc-actions-icon-wrapper">
              {copied ? <CheckIcon /> : <CopyIcon />}
            </span>
            <span className="doc-page-actions-label">
              {copied ? "Copied!" : "Copy"}
            </span>
          </button>
        </Tooltip>

        {/* Dropdown trigger */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button
              className="doc-page-actions-chevron"
              aria-label="More actions"
              aria-haspopup="menu"
            >
              <ChevronDownIcon />
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="doc-page-actions-content">
            {/* Download Markdown (single lesson) */}
            <DropdownMenuItem
              onClick={handleDownloadMarkdown}
              className={downloaded ? "doc-actions-item--success" : ""}
            >
              {downloaded ? <CheckIcon /> : <DownloadIcon />}
              <span>{downloaded ? "Downloaded!" : "Download Markdown"}</span>
              <kbd className="doc-actions-menu-shortcut">{modKey}+⇧+D</kbd>
            </DropdownMenuItem>

            {/* Chapter Download - Show to everyone, gate the action */}
            {currentChapter && (
              <DropdownMenuItem
                onClick={handleDownloadChapter}
                className={`doc-actions-chapter-item ${chapterDownloaded ? "doc-actions-item--success" : ""} ${!isLoggedIn ? "doc-actions-item--locked" : ""}`}
                disabled={chapterDownloading}
              >
                {chapterDownloading ? (
                  <LoadingIcon />
                ) : chapterDownloaded ? (
                  <CheckIcon />
                ) : (
                  <BookIcon />
                )}
                <span className="doc-actions-chapter-content">
                  <span className="doc-actions-chapter-label">
                    {chapterDownloading
                      ? downloadProgress
                      : chapterDownloaded
                        ? "Chapter Downloaded!"
                        : "Download Chapter"}
                  </span>
                  {!chapterDownloading && !chapterDownloaded && (
                    <span className="doc-actions-chapter-meta">
                      {isLoggedIn ? (
                        `(${currentChapter.lessons.length} lessons)`
                      ) : (
                        <>
                          <LockIcon /> Sign in
                        </>
                      )}
                    </span>
                  )}
                </span>
              </DropdownMenuItem>
            )}

            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={handleOpenInChatGPT}>
              <ChatGPTIcon />
              <span>Ask ChatGPT</span>
            </DropdownMenuItem>
            <DropdownMenuItem onClick={handleOpenInClaude}>
              <ClaudeIcon />
              <span>Ask Claude</span>
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={handleShare}>
              <ShareIcon />
              <span>Share</span>
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </div>
  );
}

export default DocPageActions;
