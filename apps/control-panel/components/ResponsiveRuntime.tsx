'use client';

import { useEffect } from 'react';

export function ResponsiveRuntime() {
  useEffect(() => {
    const updateViewportState = () => {
      const width = window.innerWidth;
      const orientation = window.innerWidth >= window.innerHeight ? 'landscape' : 'portrait';
      const bodyClasses = document.body.classList;

      bodyClasses.remove('mobile', 'tablet', 'desktop');
      if (width < 768) {
        bodyClasses.add('mobile');
      } else if (width < 1024) {
        bodyClasses.add('tablet');
      } else {
        bodyClasses.add('desktop');
      }

      document.querySelector('[data-testid="main-layout"]')?.setAttribute('data-orientation', orientation);
    };

    updateViewportState();
    window.addEventListener('resize', updateViewportState);
    window.addEventListener('orientationchange', updateViewportState);

    return () => {
      window.removeEventListener('resize', updateViewportState);
      window.removeEventListener('orientationchange', updateViewportState);
    };
  }, []);

  return null;
}
