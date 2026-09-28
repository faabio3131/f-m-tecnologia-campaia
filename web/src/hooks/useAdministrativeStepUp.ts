"use client";

import { useCallback, useState } from "react";
import { ApiClientError } from "../lib/api/client";
import { isTestIdentityModeEnabled } from "../lib/auth/test-identity-client";

const TEST_STEP_UP_HEADER_VALUE = "f2-web-test-step-up";

export function useAdministrativeStepUp() {
  const testMode = isTestIdentityModeEnabled();
  const [stepUpValue, setStepUpValue] = useState<string | null>(null);
  const [sessionElevated, setSessionElevated] = useState(false);
  const [stepUpMessage, setStepUpMessage] = useState<string | null>(null);

  const ready = testMode || stepUpValue !== null || sessionElevated;

  const headers = useCallback((): Record<string, string> => {
    if (testMode) return { "x-step-up-token": TEST_STEP_UP_HEADER_VALUE };
    return stepUpValue ? { "x-step-up-token": stepUpValue } : {};
  }, [stepUpValue, testMode]);

  const onIdToken = useCallback(async (idToken: string) => {
    setStepUpValue(idToken);
    setSessionElevated(false);
    setStepUpMessage(null);
  }, []);

  const consumePresentedToken = useCallback(() => {
    // O backend persiste a elevacao na sessao por STEP_UP_MAX_AGE. O ID token usado
    // para provar a reautenticacao nao precisa ficar retido no browser depois do sucesso.
    if (!testMode) {
      setStepUpValue(null);
      setSessionElevated(true);
    }
  }, [testMode]);

  const noteError = useCallback((error: unknown) => {
    if (error instanceof ApiClientError && error.code === "STEP_UP_REQUIRED") {
      setSessionElevated(false);
      setStepUpMessage(
        "Reautentique com o Google para executar esta operação administrativa.",
      );
      return;
    }
    setStepUpMessage(null);
  }, []);

  return {
    testMode,
    ready,
    headers,
    onIdToken,
    consumePresentedToken,
    noteError,
    stepUpMessage,
  };
}
