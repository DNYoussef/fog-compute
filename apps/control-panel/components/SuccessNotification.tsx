'use client';

import { Toaster, toast, Toast } from 'react-hot-toast';
import { ReactNode } from 'react';

/**
 * NotificationToaster Component
 *
 * Configures and renders the react-hot-toast Toaster with custom styling
 * and data-testid attributes for E2E testing.
 *
 * Should be placed in the root layout to ensure notifications are displayed
 * across all pages.
 */
export function NotificationToaster() {
  return (
    <Toaster
      position="top-right"
      toastOptions={{
        duration: 5000,
        style: {
          background: '#0a0e27',
          color: '#fff',
          border: '1px solid rgba(255, 255, 255, 0.1)',
          borderRadius: '8px',
          padding: '16px',
          fontSize: '14px',
          maxWidth: '500px',
        },
        success: {
          iconTheme: {
            primary: '#10b981',
            secondary: '#fff',
          },
        },
        error: {
          iconTheme: {
            primary: '#ef4444',
            secondary: '#fff',
          },
        },
      }}
    >
      {(t: Toast) => {
        // Add data-testid based on toast type
        const testId = t.type === 'success'
          ? 'success-notification'
          : t.type === 'error'
          ? 'error-notification'
          : t.type === 'loading'
          ? 'loading-notification'
          : 'notification';

        return (
          <div
            data-testid={testId}
            data-toast-id={t.id}
            data-toast-type={t.type}
            className={`
              ${t.visible ? 'animate-enter' : 'animate-leave'}
              flex items-center gap-3 w-full
            `}
            style={{
              animation: t.visible
                ? 'toast-enter 0.2s ease-out'
                : 'toast-leave 0.15s ease-in forwards',
            }}
          >
            {/* Toast icon */}
            {t.icon && <span className="flex-shrink-0">{t.icon}</span>}

            {/* Toast message */}
            <div className="flex-1" data-testid="notification-message">
              {typeof t.message === 'function'
                ? t.message(t)
                : t.message}
            </div>

            {/* Close button */}
            <button
              onClick={() => toast.dismiss(t.id)}
              className="flex-shrink-0 text-gray-400 hover:text-white transition-colors"
              data-testid="notification-close"
              aria-label="Close notification"
            >
              <svg
                className="w-4 h-4"
                fill="none"
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="2"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path d="M6 18L18 6M6 6l12 12"></path>
              </svg>
            </button>
          </div>
        );
      }}
    </Toaster>
  );
}

/**
 * Notification Helper Functions
 *
 * These functions provide a simple API for showing notifications
 * throughout the application with consistent styling and behavior.
 */

export interface NotificationOptions {
  duration?: number;
  position?: 'top-left' | 'top-center' | 'top-right' | 'bottom-left' | 'bottom-center' | 'bottom-right';
  icon?: ReactNode;
  id?: string;
}

/**
 * Show a success notification
 *
 * @param message - The message to display
 * @param options - Optional configuration
 * @returns Toast ID for programmatic control
 *
 * @example
 * showSuccess('Resource limits updated successfully');
 */
export const showSuccess = (message: string, options?: NotificationOptions): string => {
  return toast.success(message, {
    duration: options?.duration ?? 5000,
    position: options?.position,
    icon: options?.icon,
    id: options?.id,
  });
};

/**
 * Show an error notification
 *
 * @param message - The error message to display
 * @param options - Optional configuration
 * @returns Toast ID for programmatic control
 *
 * @example
 * showError('Failed to deploy node: Connection timeout');
 */
export const showError = (message: string, options?: NotificationOptions): string => {
  return toast.error(message, {
    duration: options?.duration ?? 5000,
    position: options?.position,
    icon: options?.icon,
    id: options?.id,
  });
};

/**
 * Show a warning notification
 *
 * @param message - The warning message to display
 * @param options - Optional configuration
 * @returns Toast ID for programmatic control
 *
 * @example
 * showWarning('Node performance degraded - check system resources');
 */
export const showWarning = (message: string, options?: NotificationOptions): string => {
  return toast(message, {
    duration: options?.duration ?? 5000,
    position: options?.position,
    icon: options?.icon ?? '⚠️',
    id: options?.id,
    style: {
      background: '#0a0e27',
      color: '#fff',
      border: '1px solid #f59e0b',
    },
  });
};

/**
 * Show an info notification
 *
 * @param message - The info message to display
 * @param options - Optional configuration
 * @returns Toast ID for programmatic control
 *
 * @example
 * showInfo('Node discovery in progress...');
 */
export const showInfo = (message: string, options?: NotificationOptions): string => {
  return toast(message, {
    duration: options?.duration ?? 5000,
    position: options?.position,
    icon: options?.icon ?? 'ℹ️',
    id: options?.id,
    style: {
      background: '#0a0e27',
      color: '#fff',
      border: '1px solid #3b82f6',
    },
  });
};

/**
 * Show a loading notification
 *
 * @param message - The loading message to display
 * @param options - Optional configuration
 * @returns Toast ID for programmatic control (use to dismiss later)
 *
 * @example
 * const loadingId = showLoading('Deploying node...');
 * // ... after operation completes
 * toast.dismiss(loadingId);
 * showSuccess('Node deployed successfully');
 */
export const showLoading = (message: string, options?: NotificationOptions): string => {
  return toast.loading(message, {
    duration: Infinity, // Loading toasts don't auto-dismiss
    position: options?.position,
    id: options?.id,
  });
};

/**
 * Show a promise-based notification
 *
 * Automatically shows loading, success, or error states based on promise resolution
 *
 * @param promise - The promise to track
 * @param messages - Messages for each state
 * @param options - Optional configuration
 *
 * @example
 * showPromise(
 *   deployNode(nodeId),
 *   {
 *     loading: 'Deploying node...',
 *     success: 'Node deployed successfully',
 *     error: (err) => `Deployment failed: ${err.message}`
 *   }
 * );
 */
export const showPromise = <T,>(
  promise: Promise<T>,
  messages: {
    loading: string;
    success: string | ((data: T) => string);
    error: string | ((error: Error) => string);
  },
  options?: NotificationOptions
): Promise<T> => {
  return toast.promise(
    promise,
    {
      loading: messages.loading,
      success: messages.success,
      error: messages.error,
    },
    {
      duration: options?.duration ?? 5000,
      position: options?.position,
      id: options?.id,
    }
  );
};

/**
 * Dismiss a specific notification or all notifications
 *
 * @param toastId - Optional toast ID to dismiss specific notification
 *
 * @example
 * dismissNotification(); // Dismiss all
 * dismissNotification(toastId); // Dismiss specific
 */
export const dismissNotification = (toastId?: string): void => {
  if (toastId) {
    toast.dismiss(toastId);
  } else {
    toast.dismiss();
  }
};

/**
 * Check if a notification is currently visible
 *
 * @param toastId - Toast ID to check
 * @returns boolean indicating if toast is visible
 */
export const isNotificationVisible = (toastId: string): boolean => {
  // This is a helper for testing/debugging
  return document.querySelector(`[data-toast-id="${toastId}"]`) !== null;
};

// Export toast utilities for advanced usage
export { toast };
