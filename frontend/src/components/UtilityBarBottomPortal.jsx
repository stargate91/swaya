import { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';

export default function UtilityBarBottomPortal({ children, side = 'left', enabled = true }) {
  const [targetEl, setTargetEl] = useState(null);

  useEffect(() => {
    if (enabled) {
      const selector = side === 'left' ? '.shell__utility-bar-bottom-left' : '.shell__utility-bar-bottom-right';
      setTargetEl(document.querySelector(selector));
    } else {
      setTargetEl(null);
    }
  }, [enabled, side]);

  if (!targetEl) return null;

  return createPortal(children, targetEl);
}
