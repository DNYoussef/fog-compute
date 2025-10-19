/** @type {import('jest').Config} */
const config = {
  // Test environment
  testEnvironment: 'jsdom',

  // Setup files
  setupFilesAfterEnv: ['<rootDir>/tests/setup.ts'],

  // Module paths - DISABLED: tests require unimplemented modules
  // roots: ['<rootDir>/tests/typescript'],
  roots: ['<rootDir>/src'],

  // Transform files
  transform: {
    '^.+\\.tsx?$': ['ts-jest', {
      tsconfig: {
        jsx: 'react',
        esModuleInterop: true,
        allowSyntheticDefaultImports: true,
      },
    }],
  },

  // Module name mapper for path aliases
  moduleNameMapper: {
    '^@/(.*)$': '<rootDir>/apps/control-panel/$1',
    '^@components/(.*)$': '<rootDir>/apps/control-panel/components/$1',
    '^@hooks/(.*)$': '<rootDir>/apps/control-panel/hooks/$1',
    '^@bitchat/(.*)$': '<rootDir>/apps/bitchat/$1',
    '\\.(css|less|scss|sass)$': 'identity-obj-proxy',
  },

  // Test match patterns
  testMatch: [
    '**/__tests__/**/*.+(ts|tsx|js)',
    '**/?(*.)+(spec|test).+(ts|tsx|js)',
  ],

  // Coverage configuration
  collectCoverageFrom: [
    'apps/*/components/**/*.{ts,tsx}',
    'apps/*/hooks/**/*.{ts,tsx}',
    'apps/*/lib/**/*.{ts,tsx}',
    '!**/*.d.ts',
    '!**/node_modules/**',
    '!**/.next/**',
  ],

  // Coverage threshold (note: singular not plural)
  coverageThreshold: {
    global: {
      statements: 80,
      branches: 75,
      functions: 80,
      lines: 80,
    },
  },

  // Coverage reporters
  coverageReporters: ['text', 'lcov', 'html', 'json-summary'],

  // Test timeout
  testTimeout: 10000,

  // Globals
  globals: {
    'ts-jest': {
      isolatedModules: true,
    },
  },

  // Clear mocks between tests
  clearMocks: true,
  resetMocks: true,
  restoreMocks: true,

  // Verbose output
  verbose: true,

  // Max workers for parallel execution
  maxWorkers: '50%',
};

module.exports = config;