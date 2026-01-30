/**
 * usePersonalization Hook
 *
 * Provides AI-powered lesson personalization by calling the AgentFactory API.
 * Uses streaming for real-time content display.
 *
 * Features:
 * - Streams content as it generates (better UX)
 * - Caches results globally (deduplication)
 * - Auto-saves to backend after streaming
 * - Uses stored user preferences from onboarding
 * - Redirects to onboarding if user hasn't set preferences
 */

import { useState, useCallback, useRef } from "react";
import useDocusaurusContext from "@docusaurus/useDocusaurusContext";
import { useUserPreferences } from "./useUserPreferences";

interface PersonalizationResult {
  selectedInterest: string;
  analogyLogic: string;
  personalizedContent: string;
  cached: boolean;
  generatedAt: string;
}

interface UsePersonalizationReturn {
  personalize: (lessonId: string, lessonContent: string) => Promise<void>;
  result: PersonalizationResult | null;
  streamingContent: string;
  loading: boolean;
  error: string | null;
  reset: () => void;
  needsOnboarding: boolean;
  redirectToOnboarding: () => void;
}

/**
 * Hook for personalizing lesson content via AgentFactory API with streaming.
 */
export function usePersonalization(): UsePersonalizationReturn {
  const { siteConfig } = useDocusaurusContext();
  const { preferences, hasOnboarded, checkOnboarding } = useUserPreferences();

  const [result, setResult] = useState<PersonalizationResult | null>(null);
  const [streamingContent, setStreamingContent] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Abort controller for cancellation
  const abortControllerRef = useRef<AbortController | null>(null);

  // Get API URL from config or use default
  const agentFactoryApiUrl =
    (siteConfig.customFields?.agentFactoryApiUrl as string) ||
    "http://localhost:8080";

  /**
   * Redirect user to onboarding page, storing current URL for return.
   */
  const redirectToOnboarding = useCallback(() => {
    if (typeof window !== "undefined") {
      // Store current URL to return after onboarding (but not if already on onboarding)
      if (!window.location.pathname.includes("/onboarding")) {
        localStorage.setItem("onboarding_return_url", window.location.href);
      }
      window.location.href = "/onboarding";
    }
  }, []);

  const personalize = useCallback(
    async (lessonId: string, lessonContent: string) => {
      // Cancel any existing request
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }

      // Reset state
      setLoading(true);
      setError(null);
      setResult(null);
      setStreamingContent("");

      // Check authentication - use id_token (JWT) not access_token (opaque)
      // Better Auth uses opaque access tokens, but id_token is a JWT verifiable via JWKS
      const idToken =
        typeof window !== "undefined"
          ? localStorage.getItem("ainative_id_token")
          : null;

      if (!idToken) {
        setError("Please sign in to personalize content");
        setLoading(false);
        return;
      }

      // Check if user has completed onboarding - returns BOTH status and preferences
      // This avoids React state timing issues where preferences would be stale
      const onboardingResult = await checkOnboarding();

      if (!onboardingResult.isOnboarded) {
        setError("Please complete onboarding to personalize content");
        setLoading(false);
        // Auto-redirect to onboarding
        redirectToOnboarding();
        return;
      }

      // Create new abort controller
      abortControllerRef.current = new AbortController();

      try {
        // Use preferences from the onboarding check result (NOT React state)
        // This ensures we always have the correct values, avoiding timing issues
        const userPrefs = onboardingResult.preferences;
        const gradeLevel = userPrefs?.gradeLevel || "college";
        // Use first interest from user's preferences
        const interestTag = userPrefs?.interests?.[0] || "programming";

        const response = await fetch(
          `${agentFactoryApiUrl}/api/personalize/stream`,
          {
            method: "POST",
            headers: {
              Authorization: `Bearer ${idToken}`,
              "Content-Type": "application/json",
            },
            body: JSON.stringify({
              lessonId,
              lessonContent,
              gradeLevel,
              interestTag,
            }),
            signal: abortControllerRef.current.signal,
          },
        );

        if (!response.ok) {
          if (response.status === 401) {
            setError("Session expired. Please sign in again.");
          } else if (response.status === 503) {
            setError(
              "Content generation is temporarily unavailable. Please try again later.",
            );
          } else {
            const errorData = await response.json().catch(() => ({}));
            setError(errorData.detail || "Failed to personalize content");
          }
          setLoading(false);
          return;
        }

        // Read the stream
        const reader = response.body?.getReader();
        if (!reader) {
          setError("Streaming not supported");
          setLoading(false);
          return;
        }

        const decoder = new TextDecoder();
        let accumulatedContent = "";
        let finalMetadata: Partial<PersonalizationResult> = {};

        while (true) {
          const { done, value } = await reader.read();

          if (done) break;

          const chunk = decoder.decode(value, { stream: true });

          // Parse SSE events (format: "data: {...}\n\n")
          const lines = chunk.split("\n");

          for (const line of lines) {
            if (line.startsWith("data: ")) {
              try {
                const data = JSON.parse(line.slice(6));

                switch (data.type) {
                  case "chunk":
                    // Append streaming content
                    accumulatedContent += data.content;
                    setStreamingContent(accumulatedContent);
                    break;

                  case "cached":
                    // Full cached content received
                    setResult({
                      selectedInterest: data.selectedInterest,
                      analogyLogic: data.analogyLogic,
                      personalizedContent: data.personalizedContent,
                      cached: true,
                      generatedAt: data.generatedAt,
                    });
                    setStreamingContent(data.personalizedContent);
                    setLoading(false);
                    return;

                  case "complete":
                    // Streaming complete, set final result
                    finalMetadata = {
                      selectedInterest: data.selectedInterest,
                      analogyLogic: data.analogyLogic,
                      cached: false,
                      generatedAt: data.generatedAt,
                    };
                    break;

                  case "error":
                    setError(data.message || "Generation failed");
                    setLoading(false);
                    return;
                }
              } catch (parseError) {
                // Ignore parse errors for incomplete chunks
                console.debug("SSE parse skip:", line);
              }
            }
          }
        }

        // Set final result with accumulated content
        if (accumulatedContent) {
          setResult({
            selectedInterest:
              finalMetadata.selectedInterest ||
              userPrefs?.interests?.[0] ||
              "Programming",
            analogyLogic: finalMetadata.analogyLogic || "",
            personalizedContent: accumulatedContent,
            cached: false,
            generatedAt: finalMetadata.generatedAt || new Date().toISOString(),
          });
        }
      } catch (err) {
        if (err instanceof Error && err.name === "AbortError") {
          // Request was cancelled, don't show error
          return;
        }
        console.error("Personalization error:", err);
        setError(
          err instanceof Error
            ? err.message
            : "Network error. Please try again.",
        );
      } finally {
        setLoading(false);
      }
    },
    [agentFactoryApiUrl, checkOnboarding, redirectToOnboarding],
  );

  const reset = useCallback(() => {
    // Cancel any in-flight request
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    setResult(null);
    setStreamingContent("");
    setError(null);
    setLoading(false);
  }, []);

  return {
    personalize,
    result,
    streamingContent,
    loading,
    error,
    reset,
    needsOnboarding: !hasOnboarded,
    redirectToOnboarding,
  };
}

export default usePersonalization;
