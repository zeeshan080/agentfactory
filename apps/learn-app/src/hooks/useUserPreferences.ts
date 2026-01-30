/**
 * useUserPreferences Hook
 *
 * Manages user preferences for content personalization.
 * Fetches preferences from AgentFactory API and saves onboarding data.
 *
 * Features:
 * - Checks onboarding status from database
 * - Saves preferences after onboarding
 * - In-memory caching (within session only)
 */

import { useState, useCallback } from "react";
import useDocusaurusContext from "@docusaurus/useDocusaurusContext";

export type GradeLevel =
  | "elementary"
  | "middle-school"
  | "high-school"
  | "college";

export interface UserPreferences {
  userId: string;
  gradeLevel: GradeLevel;
  interests: string[];
  onboardedAt: string;
}

export interface OnboardingCheckResult {
  isOnboarded: boolean;
  preferences: UserPreferences | null;
}

interface UseUserPreferencesReturn {
  preferences: UserPreferences | null;
  saving: boolean;
  error: string | null;
  hasOnboarded: boolean;
  checkOnboarding: () => Promise<OnboardingCheckResult>;
  savePreferences: (
    gradeLevel: GradeLevel,
    interests: string[],
  ) => Promise<boolean>;
}

// In-memory cache (resets on page reload - that's fine, we'll check DB)
let cachedPreferences: UserPreferences | null = null;
let cachedOnboardingStatus: boolean | null = null;

/**
 * Hook for managing user preferences for personalization.
 */
export function useUserPreferences(): UseUserPreferencesReturn {
  const { siteConfig } = useDocusaurusContext();

  const [preferences, setPreferences] = useState<UserPreferences | null>(
    cachedPreferences,
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasOnboarded, setHasOnboarded] = useState(
    cachedOnboardingStatus ?? false,
  );

  // Get API URL from config
  const agentFactoryApiUrl =
    (siteConfig.customFields?.agentFactoryApiUrl as string) ||
    "http://localhost:8080";

  // Get ID token for authentication
  const getIdToken = useCallback((): string | null => {
    if (typeof window === "undefined") return null;
    return localStorage.getItem("ainative_id_token");
  }, []);

  /**
   * Check if user has completed onboarding by calling the database.
   * Returns both the onboarding status AND the preferences (to avoid React state timing issues).
   */
  const checkOnboarding =
    useCallback(async (): Promise<OnboardingCheckResult> => {
      // Return memory-cached result if available
      if (cachedOnboardingStatus !== null) {
        setHasOnboarded(cachedOnboardingStatus);
        if (cachedPreferences) {
          setPreferences(cachedPreferences);
        }
        return {
          isOnboarded: cachedOnboardingStatus,
          preferences: cachedPreferences,
        };
      }

      const idToken = getIdToken();

      if (!idToken) {
        setHasOnboarded(false);
        cachedOnboardingStatus = false;
        return { isOnboarded: false, preferences: null };
      }

      try {
        const response = await fetch(
          `${agentFactoryApiUrl}/api/preferences/status`,
          {
            method: "GET",
            headers: {
              Authorization: `Bearer ${idToken}`,
            },
          },
        );

        if (!response.ok) {
          if (response.status === 401) {
            setError("Session expired. Please sign in again.");
          }
          setHasOnboarded(false);
          cachedOnboardingStatus = false;
          return { isOnboarded: false, preferences: null };
        }

        const data = await response.json();

        setHasOnboarded(data.hasOnboarded);
        cachedOnboardingStatus = data.hasOnboarded;

        if (data.preferences) {
          setPreferences(data.preferences);
          cachedPreferences = data.preferences;
        }

        return {
          isOnboarded: data.hasOnboarded,
          preferences: data.preferences || null,
        };
      } catch (err) {
        console.error("Error checking onboarding status:", err);
        setError("Failed to check onboarding status");
        return { isOnboarded: false, preferences: null };
      }
    }, [agentFactoryApiUrl, getIdToken]);

  /**
   * Save user preferences after onboarding.
   * Returns true on success, false on failure.
   */
  const savePreferences = useCallback(
    async (gradeLevel: GradeLevel, interests: string[]): Promise<boolean> => {
      const idToken = getIdToken();

      if (!idToken) {
        setError("Please sign in to save preferences");
        return false;
      }

      setSaving(true);
      setError(null);

      try {
        const response = await fetch(`${agentFactoryApiUrl}/api/preferences`, {
          method: "POST",
          headers: {
            Authorization: `Bearer ${idToken}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            gradeLevel,
            interests,
          }),
        });

        if (!response.ok) {
          if (response.status === 401) {
            setError("Session expired. Please sign in again.");
          } else {
            const errorData = await response.json().catch(() => ({}));
            setError(errorData.detail || "Failed to save preferences");
          }
          return false;
        }

        const data: UserPreferences = await response.json();

        setPreferences(data);
        setHasOnboarded(true);
        cachedPreferences = data;
        cachedOnboardingStatus = true;

        return true;
      } catch (err) {
        console.error("Error saving preferences:", err);
        setError(
          err instanceof Error
            ? err.message
            : "Network error. Please try again.",
        );
        return false;
      } finally {
        setSaving(false);
      }
    },
    [agentFactoryApiUrl, getIdToken],
  );

  return {
    preferences,
    saving,
    error,
    hasOnboarded,
    checkOnboarding,
    savePreferences,
  };
}

/**
 * Clear cached preferences (call on logout).
 */
export function clearPreferencesCache(): void {
  cachedPreferences = null;
  cachedOnboardingStatus = null;
}

export default useUserPreferences;
