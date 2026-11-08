import React, { Suspense } from 'react';
import { RelayEnvironmentProvider } from 'react-relay';
import { render, act, waitFor } from '@testing-library/react';
import { createMockEnvironment, MockPayloadGenerator } from 'relay-test-utils';

export function createEnv() {
  return createMockEnvironment();
}

export function renderWithRelay(ui, env) {
  return render(
    <RelayEnvironmentProvider environment={env}>
      <Suspense fallback={<div data-testid="relay-loading" />}>
        {ui}
      </Suspense>
    </RelayEnvironmentProvider>
  );
}

/**
 * Queue a resolver so that when execute() is subscribed it auto-resolves.
 * Must be called BEFORE the component renders (before loadQuery fires).
 */
export function queueResolver(env, mockResolvers = {}) {
  env.mock.queueOperationResolver(operation =>
    MockPayloadGenerator.generate(operation, mockResolvers)
  );
}

/**
 * Queue, render, and flush — returns the same result object as render().
 * Use for tests that want to assert on resolved data immediately.
 */
export async function renderResolved(ui, env, mockResolvers = {}) {
  queueResolver(env, mockResolvers);
  const result = renderWithRelay(ui, env);
  await act(async () => {});
  return result;
}

/**
 * Resolve the most-recently-registered Relay operation and flush React updates.
 * Use for components where the query is issued after the initial render.
 */
export async function resolveOperation(env, mockResolvers = {}) {
  await waitFor(() => {
    expect(env.mock.getAllOperations().length).toBeGreaterThan(0);
  });
  await act(async () => {
    env.mock.resolveMostRecentOperation(operation =>
      MockPayloadGenerator.generate(operation, mockResolvers)
    );
  });
}
