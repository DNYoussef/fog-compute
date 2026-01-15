/**
 * Jest Setup Library Component - Verification Test
 * =================================================
 *
 * Simple tests to verify the jest-setup library is working correctly.
 * Run with: npm test -- --testPathPattern=jest-setup
 */

import { matchers, toBeValidJSON, toBeWithinRange, toBeSorted, toHaveKeys } from './matchers';
import { configure, getConfig, mockAPIResponse, mockErrorResponse, createMockFetch } from './setup';

// Extend Jest matchers
expect.extend(matchers);

describe('Jest Setup Library - Matchers', () => {
  describe('toBeValidJSON', () => {
    it('should pass for valid JSON strings', () => {
      expect('{"key": "value"}').toBeValidJSON();
      expect('[]').toBeValidJSON();
      expect('null').toBeValidJSON();
      expect('"string"').toBeValidJSON();
      expect('123').toBeValidJSON();
    });

    it('should fail for invalid JSON strings', () => {
      expect(() => {
        expect('not json').toBeValidJSON();
      }).toThrow();

      expect(() => {
        expect('{invalid}').toBeValidJSON();
      }).toThrow();
    });
  });

  describe('toBeWithinRange', () => {
    it('should pass for numbers within range', () => {
      expect(5).toBeWithinRange(1, 10);
      expect(1).toBeWithinRange(1, 10);
      expect(10).toBeWithinRange(1, 10);
    });

    it('should fail for numbers outside range', () => {
      expect(() => {
        expect(0).toBeWithinRange(1, 10);
      }).toThrow();

      expect(() => {
        expect(11).toBeWithinRange(1, 10);
      }).toThrow();
    });
  });

  describe('toBeSorted', () => {
    it('should pass for sorted arrays', () => {
      expect([1, 2, 3, 4, 5]).toBeSorted();
      expect(['a', 'b', 'c']).toBeSorted();
      expect([]).toBeSorted();
      expect([1]).toBeSorted();
    });

    it('should fail for unsorted arrays', () => {
      expect(() => {
        expect([3, 1, 2]).toBeSorted();
      }).toThrow();
    });
  });

  describe('toHaveKeys', () => {
    it('should pass when object has all keys', () => {
      expect({ a: 1, b: 2, c: 3 }).toHaveKeys(['a', 'b']);
      expect({ name: 'test', id: '123' }).toHaveKeys(['name', 'id']);
    });

    it('should fail when object is missing keys', () => {
      expect(() => {
        expect({ a: 1 }).toHaveKeys(['a', 'b']);
      }).toThrow();
    });
  });
});

describe('Jest Setup Library - Configuration', () => {
  beforeEach(() => {
    // Reset to defaults
    configure({
      enableMSW: false,
      enableResizeObserver: true,
      enableIntersectionObserver: true,
      enableMatchMedia: true,
      enableStorage: true,
      enableScroll: true,
      enableFetch: true,
      apiBaseUrl: 'http://localhost:8000',
    });
  });

  it('should return default configuration', () => {
    const config = getConfig();
    expect(config.enableMSW).toBe(false);
    expect(config.enableResizeObserver).toBe(true);
    expect(config.apiBaseUrl).toBe('http://localhost:8000');
  });

  it('should allow configuration changes', () => {
    configure({ enableMSW: true, apiBaseUrl: 'http://api.test.com' });
    const config = getConfig();
    expect(config.enableMSW).toBe(true);
    expect(config.apiBaseUrl).toBe('http://api.test.com');
  });
});

describe('Jest Setup Library - Mock Utilities', () => {
  describe('mockAPIResponse', () => {
    it('should create a successful response', async () => {
      const data = { users: [{ id: '1', name: 'Test' }] };
      const response = mockAPIResponse(data);

      expect(response.ok).toBe(true);
      expect(response.status).toBe(200);
      expect(await response.json()).toEqual(data);
    });

    it('should allow custom status and ok values', async () => {
      const response = mockAPIResponse({ error: 'Bad request' }, { status: 400, ok: false });

      expect(response.ok).toBe(false);
      expect(response.status).toBe(400);
    });
  });

  describe('mockErrorResponse', () => {
    it('should create an error response', async () => {
      const response = mockErrorResponse(404, 'Not found');

      expect(response.ok).toBe(false);
      expect(response.status).toBe(404);
      expect(await response.json()).toEqual({ error: 'Not found' });
    });
  });

  describe('createMockFetch', () => {
    it('should return configured responses based on URL', async () => {
      configure({ apiBaseUrl: '' });
      const mockFetch = createMockFetch({
        '/api/users': { data: [{ id: '1' }] },
        '/api/projects': { data: [] },
      });

      const usersResponse = await mockFetch('/api/users');
      expect(await usersResponse.json()).toEqual({ data: [{ id: '1' }] });

      const projectsResponse = await mockFetch('/api/projects');
      expect(await projectsResponse.json()).toEqual({ data: [] });
    });

    it('should return 404 for unmatched routes', async () => {
      configure({ apiBaseUrl: '' });
      const mockFetch = createMockFetch({
        '/api/users': { data: [] },
      });

      const response = await mockFetch('/api/unknown');
      expect(response.status).toBe(404);
    });
  });
});

describe('Jest Setup Library - Integration', () => {
  it('should have all matchers available', () => {
    expect(matchers).toHaveProperty('toBeValidJSON');
    expect(matchers).toHaveProperty('toHaveBeenCalledWithMatch');
    expect(matchers).toHaveProperty('toBeWithinRange');
    expect(matchers).toHaveProperty('toMatchAPIResponse');
    expect(matchers).toHaveProperty('toBeSorted');
    expect(matchers).toHaveProperty('toHaveKeys');
  });
});
