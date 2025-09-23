/**
 * Network Status Component
 * Display mesh network health and connectivity metrics
 */

import React from 'react';
import { MeshStatus } from '../types';

interface NetworkStatusProps {
  status: MeshStatus;
  peerCount: number;
  isDiscovering: boolean;
}

export const NetworkStatus: React.FC<NetworkStatusProps> = ({
  status,
  peerCount,
  isDiscovering
}) => {
  const getHealthText = (health: string) => {
    switch (health) {
      case 'good': return 'Excellent';
      case 'fair': return 'Good';
      case 'poor': return 'Poor';
      default: return 'Unknown';
    }
  };

  return (
    <div className={`network-status ${status.health}`}>
      <div className="status-header">
        <h4>Network Status</h4>
        {isDiscovering && (
          <div className="discovering-indicator">
            <span className="spinner">Discovering...</span>
          </div>
        )}
      </div>

      <div className="status-grid">
        <div className="status-item">
          <div className="status-details">
            <div className="status-label">Health</div>
            <div className="status-value">{getHealthText(status.health)}</div>
          </div>
        </div>

        <div className="status-item">
          <div className="status-details">
            <div className="status-label">Connected</div>
            <div className="status-value">{peerCount} peers</div>
          </div>
        </div>

        <div className="status-item">
          <div className="status-details">
            <div className="status-label">Signal</div>
            <div className="status-value">{status.connectivity.toFixed(0)}%</div>
          </div>
        </div>

        <div className="status-item">
          <div className="status-details">
            <div className="status-label">Latency</div>
            <div className="status-value">{status.latency.toFixed(0)} ms</div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default NetworkStatus;