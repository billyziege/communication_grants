import '@testing-library/jest-dom';

// relay-test-utils was written for Jest and calls jest.fn() internally;
// vitest's `vi` is a drop-in replacement so expose it as `jest` globally.
global.jest = vi;

// jsdom's Blob/File may not implement .text() — polyfill it.
if (typeof Blob !== 'undefined' && !Blob.prototype.text) {
  Blob.prototype.text = function () {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result);
      reader.onerror = () => reject(reader.error);
      reader.readAsText(this);
    });
  };
}

// ResizeObserver is used internally by Radix UI
global.ResizeObserver = class {
  observe() {}
  unobserve() {}
  disconnect() {}
};

// matchMedia is expected by some Radix components
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation(query => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
});

global.IS_REACT_ACT_ENVIRONMENT = true;
