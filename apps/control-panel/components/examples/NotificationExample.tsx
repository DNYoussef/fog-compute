'use client';

import { useState } from 'react';
import {
  showSuccess,
  showError,
  showWarning,
  showInfo,
  showLoading,
  showPromise,
  dismissNotification,
  toast,
} from '../SuccessNotification';

/**
 * NotificationExample Component
 *
 * Demonstrates all notification types and usage patterns.
 * This component can be used for testing and as a reference.
 */
export function NotificationExample() {
  const [loadingToastId, setLoadingToastId] = useState<string | null>(null);

  // Simulate async operation
  const simulateAsyncOperation = (shouldFail = false): Promise<string> => {
    return new Promise((resolve, reject) => {
      setTimeout(() => {
        if (shouldFail) {
          reject(new Error('Operation failed'));
        } else {
          resolve('Operation completed successfully');
        }
      }, 2000);
    });
  };

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <h1 className="text-3xl font-bold mb-6">Notification System Examples</h1>

      {/* Basic Notifications */}
      <section className="mb-8">
        <h2 className="text-2xl font-semibold mb-4">Basic Notifications</h2>
        <div className="grid grid-cols-2 gap-4">
          <button
            onClick={() => showSuccess('Resource limits updated successfully')}
            className="px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded-lg transition-colors"
          >
            Success Notification
          </button>

          <button
            onClick={() => showError('Failed to deploy node: Connection timeout')}
            className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg transition-colors"
          >
            Error Notification
          </button>

          <button
            onClick={() => showWarning('Node performance degraded - check resources')}
            className="px-4 py-2 bg-yellow-600 hover:bg-yellow-700 text-white rounded-lg transition-colors"
          >
            Warning Notification
          </button>

          <button
            onClick={() => showInfo('Node discovery in progress...')}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors"
          >
            Info Notification
          </button>
        </div>
      </section>

      {/* Loading Notifications */}
      <section className="mb-8">
        <h2 className="text-2xl font-semibold mb-4">Loading Notifications</h2>
        <div className="grid grid-cols-2 gap-4">
          <button
            onClick={() => {
              const id = showLoading('Deploying node...');
              setLoadingToastId(id);
            }}
            className="px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg transition-colors"
          >
            Show Loading
          </button>

          <button
            onClick={() => {
              if (loadingToastId) {
                dismissNotification(loadingToastId);
                showSuccess('Node deployed successfully');
                setLoadingToastId(null);
              }
            }}
            disabled={!loadingToastId}
            className="px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Complete Loading
          </button>
        </div>
      </section>

      {/* Promise-based Notifications */}
      <section className="mb-8">
        <h2 className="text-2xl font-semibold mb-4">Promise-based Notifications</h2>
        <div className="grid grid-cols-2 gap-4">
          <button
            onClick={() => {
              showPromise(
                simulateAsyncOperation(false),
                {
                  loading: 'Processing request...',
                  success: 'Request completed successfully',
                  error: (err) => `Request failed: ${err.message}`,
                }
              );
            }}
            className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg transition-colors"
          >
            Promise Success
          </button>

          <button
            onClick={() => {
              showPromise(
                simulateAsyncOperation(true),
                {
                  loading: 'Processing request...',
                  success: 'Request completed successfully',
                  error: (err) => `Request failed: ${err.message}`,
                }
              );
            }}
            className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg transition-colors"
          >
            Promise Error
          </button>
        </div>
      </section>

      {/* Custom Duration */}
      <section className="mb-8">
        <h2 className="text-2xl font-semibold mb-4">Custom Duration</h2>
        <div className="grid grid-cols-2 gap-4">
          <button
            onClick={() => showSuccess('This will stay for 10 seconds', { duration: 10000 })}
            className="px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded-lg transition-colors"
          >
            10 Second Duration
          </button>

          <button
            onClick={() => showInfo('This will stay for 2 seconds', { duration: 2000 })}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors"
          >
            2 Second Duration
          </button>
        </div>
      </section>

      {/* Custom Icons */}
      <section className="mb-8">
        <h2 className="text-2xl font-semibold mb-4">Custom Icons</h2>
        <div className="grid grid-cols-2 gap-4">
          <button
            onClick={() => showSuccess('Custom success icon', { icon: '🚀' })}
            className="px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded-lg transition-colors"
          >
            Custom Success Icon
          </button>

          <button
            onClick={() => showInfo('Custom info icon', { icon: '📢' })}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors"
          >
            Custom Info Icon
          </button>
        </div>
      </section>

      {/* Dismiss All */}
      <section className="mb-8">
        <h2 className="text-2xl font-semibold mb-4">Dismiss Notifications</h2>
        <div className="grid grid-cols-2 gap-4">
          <button
            onClick={() => {
              showSuccess('Notification 1');
              showInfo('Notification 2');
              showWarning('Notification 3');
            }}
            className="px-4 py-2 bg-gray-600 hover:bg-gray-700 text-white rounded-lg transition-colors"
          >
            Show Multiple
          </button>

          <button
            onClick={() => dismissNotification()}
            className="px-4 py-2 bg-gray-600 hover:bg-gray-700 text-white rounded-lg transition-colors"
          >
            Dismiss All
          </button>
        </div>
      </section>

      {/* Real-world Examples */}
      <section className="mb-8">
        <h2 className="text-2xl font-semibold mb-4">Real-world Use Cases</h2>
        <div className="grid grid-cols-2 gap-4">
          <button
            onClick={() => {
              // Simulate resource limit update
              const id = showLoading('Updating resource limits...');
              setTimeout(() => {
                dismissNotification(id);
                showSuccess('Resource limits updated: CPU 8 cores, Memory 16GB');
              }, 2000);
            }}
            className="px-4 py-2 bg-teal-600 hover:bg-teal-700 text-white rounded-lg transition-colors"
          >
            Update Resource Limits
          </button>

          <button
            onClick={() => {
              // Simulate node deployment
              showPromise(
                simulateAsyncOperation(false),
                {
                  loading: 'Deploying node to network...',
                  success: 'Node deployed successfully to us-west-1',
                  error: (err) => `Deployment failed: ${err.message}`,
                }
              );
            }}
            className="px-4 py-2 bg-teal-600 hover:bg-teal-700 text-white rounded-lg transition-colors"
          >
            Deploy Node
          </button>

          <button
            onClick={() => {
              // Simulate configuration change
              showSuccess('Configuration saved: Auto-scaling enabled');
            }}
            className="px-4 py-2 bg-teal-600 hover:bg-teal-700 text-white rounded-lg transition-colors"
          >
            Save Configuration
          </button>

          <button
            onClick={() => {
              // Simulate API operation
              showInfo('API key regenerated - please update your clients');
            }}
            className="px-4 py-2 bg-teal-600 hover:bg-teal-700 text-white rounded-lg transition-colors"
          >
            Regenerate API Key
          </button>
        </div>
      </section>

      {/* Advanced Usage */}
      <section className="mb-8">
        <h2 className="text-2xl font-semibold mb-4">Advanced Usage</h2>
        <div className="grid grid-cols-2 gap-4">
          <button
            onClick={() => {
              // Using toast directly with custom render
              toast.custom(
                (t) => (
                  <div
                    data-testid="custom-notification"
                    className={`${
                      t.visible ? 'animate-enter' : 'animate-leave'
                    } bg-gradient-to-r from-purple-600 to-pink-600 text-white px-6 py-4 rounded-lg shadow-lg`}
                  >
                    <div className="flex items-center gap-3">
                      <span className="text-2xl">✨</span>
                      <div>
                        <div className="font-bold">Custom Notification</div>
                        <div className="text-sm opacity-90">With custom styling</div>
                      </div>
                      <button
                        onClick={() => toast.dismiss(t.id)}
                        className="ml-4 text-white hover:text-gray-200"
                      >
                        ✕
                      </button>
                    </div>
                  </div>
                ),
                { duration: 5000 }
              );
            }}
            className="px-4 py-2 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 text-white rounded-lg transition-colors"
          >
            Custom Styled Toast
          </button>

          <button
            onClick={() => {
              // Show notification with unique ID
              showSuccess('Persistent notification', {
                id: 'unique-id',
                duration: Infinity
              });
            }}
            className="px-4 py-2 bg-orange-600 hover:bg-orange-700 text-white rounded-lg transition-colors"
          >
            Persistent Notification
          </button>
        </div>
      </section>
    </div>
  );
}
