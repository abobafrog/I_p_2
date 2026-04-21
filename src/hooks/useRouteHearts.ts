import { useState } from "react";


function getLevelHeartsKey(topic: string, levelIndex: number) {
  return `${topic}:${levelIndex}`;
}

export function useRouteHearts(initialHearts = 3) {
  const [hearts, setHearts] = useState(initialHearts);
  const [levelHearts, setLevelHearts] = useState<Record<string, number>>({});

  function getStoredHearts(topic: string, levelIndex: number, fallback = initialHearts) {
    return levelHearts[getLevelHeartsKey(topic, levelIndex)] ?? fallback;
  }

  function syncLevelHearts(topic: string, levelIndex: number, nextHearts: number) {
    const key = getLevelHeartsKey(topic, levelIndex);
    setLevelHearts((prev) => ({
      ...prev,
      [key]: nextHearts,
    }));
    setHearts(nextHearts);
  }

  function clearRouteHearts(topic: string) {
    const prefix = `${topic}:`;
    setLevelHearts((prev) =>
      Object.fromEntries(
        Object.entries(prev).filter(([key]) => !key.startsWith(prefix)),
      ),
    );
  }

  function resetHeartsState() {
    setHearts(initialHearts);
    setLevelHearts({});
  }

  return {
    hearts,
    setHearts,
    getStoredHearts,
    syncLevelHearts,
    clearRouteHearts,
    resetHeartsState,
  };
}
