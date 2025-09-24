'use client';

import { useEffect, useRef } from 'react';

export function TokenChart() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    canvas.width = canvas.offsetWidth;
    canvas.height = canvas.offsetHeight;

    const prices = Array.from({ length: 30 }, (_, i) => ({
      time: i,
      value: 0.08 + Math.sin(i / 5) * 0.01 + Math.random() * 0.005
    }));

    function animate() {
      if (!ctx || !canvas) return;

      ctx.clearRect(0, 0, canvas.width, canvas.height);

      const padding = 40;
      const chartWidth = canvas.width - padding * 2;
      const chartHeight = canvas.height - padding * 2;

      const maxPrice = Math.max(...prices.map(p => p.value));
      const minPrice = Math.min(...prices.map(p => p.value));
      const priceRange = maxPrice - minPrice;

      ctx.strokeStyle = 'rgba(250, 204, 21, 0.1)';
      ctx.lineWidth = 1;
      for (let i = 0; i <= 5; i++) {
        const y = padding + (chartHeight / 5) * i;
        ctx.beginPath();
        ctx.moveTo(padding, y);
        ctx.lineTo(canvas.width - padding, y);
        ctx.stroke();

        const price = maxPrice - (priceRange / 5) * i;
        ctx.fillStyle = '#9ca3af';
        ctx.font = '12px sans-serif';
        ctx.textAlign = 'right';
        ctx.fillText(`$${price.toFixed(4)}`, padding - 10, y + 4);
      }

      const gradient = ctx.createLinearGradient(0, padding, 0, canvas.height - padding);
      gradient.addColorStop(0, 'rgba(250, 204, 21, 0.3)');
      gradient.addColorStop(1, 'rgba(250, 204, 21, 0.05)');

      ctx.beginPath();
      ctx.moveTo(padding, canvas.height - padding);

      prices.forEach((point, i) => {
        const x = padding + (chartWidth / (prices.length - 1)) * i;
        const y = padding + chartHeight - ((point.value - minPrice) / priceRange) * chartHeight;

        if (i === 0) {
          ctx.lineTo(x, y);
        } else {
          ctx.lineTo(x, y);
        }
      });

      ctx.lineTo(canvas.width - padding, canvas.height - padding);
      ctx.closePath();
      ctx.fillStyle = gradient;
      ctx.fill();

      ctx.beginPath();
      ctx.moveTo(padding, padding + chartHeight - ((prices[0].value - minPrice) / priceRange) * chartHeight);

      prices.forEach((point, i) => {
        const x = padding + (chartWidth / (prices.length - 1)) * i;
        const y = padding + chartHeight - ((point.value - minPrice) / priceRange) * chartHeight;
        ctx.lineTo(x, y);
      });

      ctx.strokeStyle = '#facc15';
      ctx.lineWidth = 3;
      ctx.stroke();

      prices.forEach((point, i) => {
        const x = padding + (chartWidth / (prices.length - 1)) * i;
        const y = padding + chartHeight - ((point.value - minPrice) / priceRange) * chartHeight;

        ctx.beginPath();
        ctx.arc(x, y, 4, 0, Math.PI * 2);
        ctx.fillStyle = '#facc15';
        ctx.fill();
      });

      requestAnimationFrame(animate);
    }

    animate();
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className="w-full h-full min-h-[300px]"
      style={{ background: 'transparent' }}
    />
  );
}