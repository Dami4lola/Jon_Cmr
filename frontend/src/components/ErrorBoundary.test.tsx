import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ErrorBoundary } from './ErrorBoundary';

// Component that always throws on render
const ThrowingComponent = () => {
  throw new Error('test render error');
};

describe('ErrorBoundary', () => {
  // Suppress React's expected console.error output during error boundary tests
  beforeEach(() => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
  });

  it('renders children when no error occurs', () => {
    render(
      <ErrorBoundary>
        <div>content rendered fine</div>
      </ErrorBoundary>
    );
    expect(screen.getByText('content rendered fine')).toBeInTheDocument();
  });

  it('renders default fallback UI when a child throws', () => {
    render(
      <ErrorBoundary>
        <ThrowingComponent />
      </ErrorBoundary>
    );
    expect(screen.getByText('Something went wrong')).toBeInTheDocument();
  });

  it('renders custom fallback when provided and a child throws', () => {
    render(
      <ErrorBoundary fallback={<div>custom fallback</div>}>
        <ThrowingComponent />
      </ErrorBoundary>
    );
    expect(screen.getByText('custom fallback')).toBeInTheDocument();
  });
});
