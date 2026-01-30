import React, { useState, useEffect, useRef } from "react";
import Layout from "@theme/Layout";
import { useAuth } from "@/contexts/AuthContext";
import {
  useUserPreferences,
  type GradeLevel,
} from "@/hooks/useUserPreferences";
import { getHomeUrl } from "@/lib/url-utils";

// Available interests for personalization
const AVAILABLE_INTERESTS = [
  { id: "programming", label: "Programming", emoji: "💻" },
  { id: "gaming", label: "Gaming", emoji: "🎮" },
  { id: "sports", label: "Sports", emoji: "⚽" },
  { id: "music", label: "Music", emoji: "🎵" },
  { id: "cooking", label: "Cooking", emoji: "🍳" },
  { id: "science", label: "Science", emoji: "🔬" },
  { id: "art", label: "Art & Design", emoji: "🎨" },
  { id: "business", label: "Business", emoji: "💼" },
  { id: "movies", label: "Movies & TV", emoji: "🎬" },
  { id: "nature", label: "Nature", emoji: "🌿" },
  { id: "travel", label: "Travel", emoji: "✈️" },
  { id: "fitness", label: "Fitness", emoji: "💪" },
];

const GRADE_LEVELS: {
  value: GradeLevel;
  label: string;
  description: string;
}[] = [
  {
    value: "elementary",
    label: "Elementary",
    description: "Simple explanations with fun examples",
  },
  {
    value: "middle-school",
    label: "Middle School",
    description: "More detail with relatable comparisons",
  },
  {
    value: "high-school",
    label: "High School",
    description: "Technical concepts with real-world context",
  },
  {
    value: "college",
    label: "College / Professional",
    description: "In-depth explanations with industry terms",
  },
];

export default function OnboardingPage(): React.JSX.Element {
  const { session, isLoading: authLoading } = useAuth();
  const {
    savePreferences,
    saving: savingPrefs,
    checkOnboarding,
  } = useUserPreferences();

  const [gradeLevel, setGradeLevel] = useState<GradeLevel>("college");
  const [selectedInterests, setSelectedInterests] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [checkingStatus, setCheckingStatus] = useState(true);
  const [alreadyOnboarded, setAlreadyOnboarded] = useState(false);
  const hasChecked = useRef(false);

  // Check onboarding status from DB on mount
  useEffect(() => {
    // Only run once
    if (hasChecked.current) return;

    // Wait for auth to be ready
    if (authLoading) return;

    // Mark as checked
    hasChecked.current = true;

    // If not logged in, show the form (they'll get an error when submitting)
    if (!session) {
      setCheckingStatus(false);
      return;
    }

    // Check DB for onboarding status
    checkOnboarding()
      .then((result) => {
        if (result.isOnboarded) {
          setAlreadyOnboarded(true);
        }
        setCheckingStatus(false);
      })
      .catch(() => {
        setCheckingStatus(false);
      });
  }, [authLoading, session]);

  const toggleInterest = (interestId: string) => {
    setSelectedInterests((prev) =>
      prev.includes(interestId)
        ? prev.filter((i) => i !== interestId)
        : [...prev, interestId],
    );
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (selectedInterests.length === 0) {
      setError("Please select at least one interest");
      return;
    }

    const success = await savePreferences(gradeLevel, selectedInterests);

    if (success) {
      setSuccess(true);
      // Redirect after short delay
      setTimeout(() => {
        const returnUrl = localStorage.getItem("onboarding_return_url");
        localStorage.removeItem("onboarding_return_url");
        // Never redirect back to onboarding page
        const isOnboardingUrl = returnUrl?.includes("/onboarding");
        const targetUrl =
          returnUrl && !isOnboardingUrl ? returnUrl : getHomeUrl();
        window.location.href = targetUrl;
      }, 1500);
    } else {
      setError("Failed to save preferences. Please try again.");
    }
  };

  // Loading state (auth loading or checking onboarding status)
  if (authLoading || checkingStatus) {
    return (
      <Layout title="Loading..." description="Loading...">
        <div style={styles.container}>
          <div style={styles.spinner} />
          <style>{spinnerKeyframes}</style>
        </div>
      </Layout>
    );
  }

  // Already onboarded state - show message instead of auto-redirect
  if (alreadyOnboarded) {
    const returnUrl = localStorage.getItem("onboarding_return_url");
    localStorage.removeItem("onboarding_return_url");
    // Never redirect back to onboarding page
    const isOnboardingUrl = returnUrl?.includes("/onboarding");
    const targetUrl = returnUrl && !isOnboardingUrl ? returnUrl : getHomeUrl();

    return (
      <Layout
        title="Already Set Up"
        description="You've already completed onboarding"
      >
        <div style={styles.container}>
          <div style={styles.successIcon}>
            <svg
              width="48"
              height="48"
              viewBox="0 0 24 24"
              fill="none"
              stroke="white"
              strokeWidth="2"
            >
              <polyline points="20 6 9 17 4 12"></polyline>
            </svg>
          </div>
          <h1 style={styles.title}>You're already set up!</h1>
          <p style={styles.subtitle}>
            Your preferences are saved. Ready to continue learning?
          </p>
          <a href={targetUrl} style={styles.submitButton}>
            Continue
          </a>
        </div>
      </Layout>
    );
  }

  // Success state (just saved)
  if (success) {
    return (
      <Layout title="Welcome!" description="Your preferences have been saved">
        <div style={styles.container}>
          <div style={styles.successIcon}>
            <svg
              width="48"
              height="48"
              viewBox="0 0 24 24"
              fill="none"
              stroke="white"
              strokeWidth="2"
            >
              <polyline points="20 6 9 17 4 12"></polyline>
            </svg>
          </div>
          <h1 style={styles.title}>You're all set!</h1>
          <p style={styles.subtitle}>
            Your learning experience will now be personalized just for you.
          </p>
        </div>
      </Layout>
    );
  }

  return (
    <Layout
      title="Personalize Your Learning"
      description="Tell us about yourself to personalize your learning experience"
    >
      <div style={styles.container}>
        <div style={styles.card}>
          <h1 style={styles.title}>Personalize Your Learning</h1>
          <p style={styles.subtitle}>
            Tell us a bit about yourself so we can tailor explanations and
            examples to your interests and level.
          </p>

          <form onSubmit={handleSubmit} style={styles.form}>
            {/* Grade Level Section */}
            <div style={styles.section}>
              <h2 style={styles.sectionTitle}>What's your experience level?</h2>
              <div style={styles.gradeGrid}>
                {GRADE_LEVELS.map((level) => (
                  <button
                    key={level.value}
                    type="button"
                    onClick={() => setGradeLevel(level.value)}
                    style={{
                      ...styles.gradeButton,
                      ...(gradeLevel === level.value
                        ? styles.gradeButtonSelected
                        : {}),
                    }}
                  >
                    <span style={styles.gradeLabel}>{level.label}</span>
                    <span style={styles.gradeDescription}>
                      {level.description}
                    </span>
                  </button>
                ))}
              </div>
            </div>

            {/* Interests Section */}
            <div style={styles.section}>
              <h2 style={styles.sectionTitle}>What are you interested in?</h2>
              <p style={styles.sectionHint}>
                Select topics you enjoy — we'll use these for examples and
                analogies.
              </p>
              <div style={styles.interestsGrid}>
                {AVAILABLE_INTERESTS.map((interest) => (
                  <button
                    key={interest.id}
                    type="button"
                    onClick={() => toggleInterest(interest.id)}
                    style={{
                      ...styles.interestChip,
                      ...(selectedInterests.includes(interest.id)
                        ? styles.interestChipSelected
                        : {}),
                    }}
                  >
                    <span style={styles.interestEmoji}>{interest.emoji}</span>
                    <span>{interest.label}</span>
                  </button>
                ))}
              </div>
              {selectedInterests.length > 0 && (
                <p style={styles.selectedCount}>
                  {selectedInterests.length} selected
                </p>
              )}
            </div>

            {/* Error message */}
            {error && <div style={styles.error}>{error}</div>}

            {/* Submit button */}
            <button
              type="submit"
              disabled={savingPrefs || selectedInterests.length === 0}
              style={{
                ...styles.submitButton,
                ...(savingPrefs || selectedInterests.length === 0
                  ? styles.submitButtonDisabled
                  : {}),
              }}
            >
              {savingPrefs ? "Saving..." : "Start Learning"}
            </button>
          </form>
        </div>
      </div>
    </Layout>
  );
}

// Spinner animation keyframes
const spinnerKeyframes = `
  @keyframes spin {
    to { transform: rotate(360deg); }
  }
`;

// Inline styles (for Docusaurus compatibility)
const styles: { [key: string]: React.CSSProperties } = {
  container: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    minHeight: "70vh",
    padding: "2rem",
  },
  spinner: {
    width: "48px",
    height: "48px",
    border: "4px solid var(--ifm-color-emphasis-200)",
    borderTopColor: "var(--ifm-color-primary)",
    borderRadius: "50%",
    animation: "spin 1s linear infinite",
  },
  card: {
    maxWidth: "700px",
    width: "100%",
    padding: "2rem",
    backgroundColor: "var(--ifm-background-surface-color)",
    borderRadius: "12px",
    boxShadow: "0 4px 20px rgba(0, 0, 0, 0.1)",
  },
  title: {
    fontSize: "1.75rem",
    fontWeight: 700,
    marginBottom: "0.5rem",
    textAlign: "center" as const,
    color: "var(--ifm-font-color-base)",
  },
  subtitle: {
    fontSize: "1rem",
    color: "var(--ifm-font-color-secondary)",
    textAlign: "center" as const,
    marginBottom: "2rem",
  },
  form: {
    display: "flex",
    flexDirection: "column",
    gap: "2rem",
  },
  section: {
    display: "flex",
    flexDirection: "column",
    gap: "0.75rem",
  },
  sectionTitle: {
    fontSize: "1.1rem",
    fontWeight: 600,
    color: "var(--ifm-font-color-base)",
    margin: 0,
  },
  sectionHint: {
    fontSize: "0.875rem",
    color: "var(--ifm-font-color-secondary)",
    margin: 0,
  },
  gradeGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))",
    gap: "0.75rem",
  },
  gradeButton: {
    display: "flex",
    flexDirection: "column",
    alignItems: "flex-start",
    padding: "1rem",
    border: "2px solid var(--ifm-color-emphasis-200)",
    borderRadius: "8px",
    backgroundColor: "transparent",
    cursor: "pointer",
    transition: "all 0.2s ease",
    textAlign: "left" as const,
  },
  gradeButtonSelected: {
    borderColor: "var(--ifm-color-primary)",
    backgroundColor: "var(--ifm-color-primary-lightest)",
  },
  gradeLabel: {
    fontWeight: 600,
    fontSize: "0.95rem",
    color: "var(--ifm-font-color-base)",
  },
  gradeDescription: {
    fontSize: "0.8rem",
    color: "var(--ifm-font-color-secondary)",
    marginTop: "0.25rem",
  },
  interestsGrid: {
    display: "flex",
    flexWrap: "wrap" as const,
    gap: "0.5rem",
  },
  interestChip: {
    display: "flex",
    alignItems: "center",
    gap: "0.5rem",
    padding: "0.5rem 1rem",
    border: "2px solid var(--ifm-color-emphasis-200)",
    borderRadius: "20px",
    backgroundColor: "transparent",
    cursor: "pointer",
    transition: "all 0.2s ease",
    fontSize: "0.9rem",
    color: "var(--ifm-font-color-base)",
  },
  interestChipSelected: {
    borderColor: "var(--ifm-color-primary)",
    backgroundColor: "var(--ifm-color-primary-lightest)",
  },
  interestEmoji: {
    fontSize: "1.1rem",
  },
  selectedCount: {
    fontSize: "0.85rem",
    color: "var(--ifm-color-primary)",
    fontWeight: 500,
    marginTop: "0.5rem",
  },
  error: {
    padding: "0.75rem 1rem",
    backgroundColor: "rgba(239, 68, 68, 0.1)",
    borderRadius: "8px",
    color: "#ef4444",
    fontSize: "0.9rem",
  },
  submitButton: {
    padding: "1rem 2rem",
    backgroundColor: "var(--ifm-color-primary)",
    color: "white",
    border: "none",
    borderRadius: "8px",
    fontSize: "1rem",
    fontWeight: 600,
    cursor: "pointer",
    transition: "all 0.2s ease",
  },
  submitButtonDisabled: {
    opacity: 0.5,
    cursor: "not-allowed",
  },
  successIcon: {
    width: "80px",
    height: "80px",
    borderRadius: "50%",
    backgroundColor: "#22c55e",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    marginBottom: "1.5rem",
  },
};
