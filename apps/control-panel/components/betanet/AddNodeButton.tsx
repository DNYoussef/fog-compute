'use client';

import { Plus } from 'lucide-react';

interface AddNodeButtonProps {
  onClick: () => void;
}

export function AddNodeButton({ onClick }: AddNodeButtonProps) {
  return (
    <button
      data-testid="add-node-button"
      onClick={onClick}
      className="fixed bottom-24 right-8 md:bottom-8 bg-blue-600 hover:bg-blue-700 text-white rounded-full p-4 shadow-lg transition-all duration-200 hover:scale-110 z-40"
      aria-label="Add new node"
    >
      <Plus className="w-6 h-6" />
    </button>
  );
}
