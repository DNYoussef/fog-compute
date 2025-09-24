'use client';

import { useEffect, useRef } from 'react';

interface CircuitVisualizationProps {
  selectedCircuit: string | null;
  stats: any;
}

export function CircuitVisualization({ selectedCircuit, stats }: CircuitVisualizationProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    canvas.width = canvas.offsetWidth;
    canvas.height = canvas.offsetHeight;

    const layers = stats?.onion.layers || 3;
    const centerY = canvas.height / 2;
    const spacing = canvas.width / (layers + 2);

    function drawOnionLayer(x: number, y: number, radius: number, color: string, label: string) {
      if (!ctx) return;

      ctx.beginPath();
      ctx.arc(x, y, radius, 0, Math.PI * 2);
      ctx.fillStyle = color;
      ctx.fill();
      ctx.strokeStyle = '#fff';
      ctx.lineWidth = 3;
      ctx.stroke();

      ctx.fillStyle = '#fff';
      ctx.font = '14px sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText(label, x, y + radius + 20);
    }

    function animate() {
      if (!ctx || !canvas) return;

      ctx.clearRect(0, 0, canvas.width, canvas.height);

      const user = { x: spacing, y: centerY };
      const destination = { x: canvas.width - spacing, y: centerY };

      ctx.strokeStyle = 'rgba(168, 85, 247, 0.3)';
      ctx.lineWidth = 4;
      ctx.setLineDash([10, 5]);
      ctx.beginPath();
      ctx.moveTo(user.x, user.y);

      for (let i = 1; i <= layers; i++) {
        const x = spacing * (i + 1);
        ctx.lineTo(x, centerY);
      }
      ctx.lineTo(destination.x, destination.y);
      ctx.stroke();
      ctx.setLineDash([]);

      drawOnionLayer(user.x, user.y, 30, '#10b981', 'You');

      for (let i = 1; i <= layers; i++) {
        const x = spacing * (i + 1);
        const hue = 250 + (i * 30);
        drawOnionLayer(x, centerY, 40, `hsl(${hue}, 70%, 60%)`, `Relay ${i}`);
      }

      drawOnionLayer(destination.x, destination.y, 30, '#06b6d4', 'Exit');

      requestAnimationFrame(animate);
    }

    animate();
  }, [stats]);

  return (
    <div className="w-full h-full min-h-[500px] relative">
      <canvas
        ref={canvasRef}
        className="w-full h-full"
        style={{ background: 'transparent' }}
      />
      <div className="absolute top-4 left-4 glass rounded-lg p-4">
        <div className="text-sm text-gray-400">Encryption Layers</div>
        <div className="text-2xl font-bold text-purple-400">{stats?.onion.layers || 0}</div>
      </div>
      <div className="absolute top-4 right-4 glass rounded-lg p-4">
        <div className="text-sm text-gray-400">Active Circuits</div>
        <div className="text-2xl font-bold text-fog-cyan">{stats?.circuits.active || 0}</div>
      </div>
    </div>
  );
}