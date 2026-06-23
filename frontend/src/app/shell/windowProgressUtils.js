const PHASE_RANGES = {
  collecting: [0, 5],
  resolving: [5, 100],
  organizing: [0, 100],
  undoing: [0, 100],
};

export const clampPercent = (value) => Math.max(0, Math.min(100, value));

export const getPhaseProgress = (status) => {
  if (!status?.active) {
    return 0;
  }

  const total = Number(status.total) || 0;
  const current = Number(status.current) || 0;
  const currentFileProgress = Math.max(0, Math.min(1, Number(status.current_file_progress) || 0));
  if (total <= 0) {
    return 0;
  }

  const safeCurrent = Math.max(0, Math.min(total, current));
  const fractionalCurrent = safeCurrent >= total
    ? safeCurrent
    : Math.min(total, safeCurrent + currentFileProgress);

  return Math.max(0, Math.min(1, fractionalCurrent / total));
};

export const getScanProgress = (status) => {
  if (!status?.active) {
    return 0;
  }

  const phaseProgress = getPhaseProgress(status);
  const range = PHASE_RANGES[status.phase];

  let progress;
  if (!range) {
    progress = clampPercent(Math.round(phaseProgress * 100));
  } else {
    const [start, end] = range;
    progress = clampPercent(Math.round(start + ((end - start) * phaseProgress)));
  }

  return status.active && progress >= 100 ? 99 : progress;
};

export const formatScanRemaining = (status, progress, now = Date.now()) => {
  if (!status?.active) {
    return '--:--';
  }

  const startTime = Number(status.start_time) || 0;

  if (!startTime || progress <= 0 || progress >= 100) {
    return '--:--';
  }

  const elapsedSeconds = Math.max(0, now / 1000 - startTime);
  if (!elapsedSeconds) {
    return '--:--';
  }

  const estimatedRemaining = Math.max(0, Math.round((elapsedSeconds / progress) * (100 - progress)));
  const minutes = String(Math.floor(estimatedRemaining / 60)).padStart(2, '0');
  const seconds = String(estimatedRemaining % 60).padStart(2, '0');
  return `${minutes}:${seconds}`;
};

export const getScanTaskName = (status, t) => {
  if (!status?.active) {
    return t('progress.ready');
  }

  if (status.message) {
    return status.message;
  }

  const phaseLabelKey = `progress.scan.${status.phase}`;
  const phaseLabel = t(phaseLabelKey);
  return phaseLabel === phaseLabelKey ? t('progress.working') : phaseLabel;
};

export const getImageProgress = (status) => {
  if (!status?.active) {
    return 0;
  }

  const progress = Number(status.progress);
  if (Number.isFinite(progress)) {
    return clampPercent(Math.round(progress));
  }

  const total = Number(status.total) || 0;
  const completed = Number(status.completed) || 0;
  if (total <= 0) {
    return 0;
  }

  return clampPercent(Math.round((completed / total) * 100));
};

export const formatImageRemaining = (status) => {
  if (!status?.active) {
    return '--:--';
  }

  const progress = getImageProgress(status);
  if (progress <= 0 || progress >= 100) {
    return '--:--';
  }

  return `${Number(status.completed) || 0}/${Number(status.total) || 0}`;
};
