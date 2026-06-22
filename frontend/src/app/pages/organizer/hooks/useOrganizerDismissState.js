/* eslint-disable react-hooks/set-state-in-effect */
import { useEffect, useState } from 'react';

const EMPTY_SET = new Set();

export function useOrganizerDismissState({ organizer, scopeKey }) {
  const [dismissedByScope, setDismissedByScope] = useState({});
  const dismissedRowIds = dismissedByScope[scopeKey] || EMPTY_SET;

  useEffect(() => {
    if (!organizer) {
      return;
    }

    const validIds = new Set([
      ...(organizer.manual || []).map((item) => `item-${item.id}`),
      ...(organizer.movies || []).map((item) => `item-${item.id}`),
      ...(organizer.tv || []).map((item) => `item-${item.id}`),
      ...(organizer.collisions || []).map((item) => `item-${item.id}`),
      ...(organizer.extras || []).map((item) => `extra-${item.id}`),
    ]);

    setDismissedByScope((current) => {
      const currentScopeSet = current[scopeKey] || EMPTY_SET;
      const nextScopeSet = new Set();
      currentScopeSet.forEach((id) => {
        if (validIds.has(id)) {
          nextScopeSet.add(id);
        }
      });

      return nextScopeSet.size === currentScopeSet.size
        ? current
        : {
          ...current,
          [scopeKey]: nextScopeSet,
        };
    });
  }, [organizer, scopeKey]);

  const dismissRows = (rowIds) => {
    const validRowIds = rowIds.filter((id) => id.startsWith('item-') || id.startsWith('extra-'));
    if (validRowIds.length === 0) return;
    setDismissedByScope((current) => {
      const next = new Set(current[scopeKey] || EMPTY_SET);
      validRowIds.forEach((id) => next.add(id));
      return {
        ...current,
        [scopeKey]: next,
      };
    });
  };

  const restoreDismissedRows = () => {
    setDismissedByScope((current) => ({
      ...current,
      [scopeKey]: new Set(),
    }));
  };

  const dismissedCount = dismissedRowIds.size;

  return {
    dismissedRowIds,
    dismissedCount,
    dismissRows,
    restoreDismissedRows,
  };
}
