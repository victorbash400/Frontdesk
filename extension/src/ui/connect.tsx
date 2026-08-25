/**
 * Copyright (c) Microsoft Corporation.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

import React, { useCallback, useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { Button } from './tabItem';
import { AuthTokenSection, getOrCreateAuthToken } from './authToken';

type Status =
  | { type: 'connecting'; message: string }
  | { type: 'connected'; message: string }
  | { type: 'error'; message: string }
  | { type: 'error'; versionMismatch: { extensionVersion: string; } };

const SUPPORTED_PROTOCOL_VERSION = 2;

// Client name comes from the URL and never changes for the lifetime of this page.
const clientInfo = (() => {
  try {
    return JSON.parse(new URLSearchParams(window.location.search).get('client') || '{}').name || 'unknown';
  } catch {
    return 'unknown';
  }
})();

const ConnectApp: React.FC = () => {
  const [status, setStatus] = useState<Status | null>(null);

  const setError = useCallback((message: string) => {
    setStatus({ type: 'error', message });
  }, []);

  useEffect(() => {
    const runAsync = async () => {
      const params = new URLSearchParams(window.location.search);
      const relayUrl = params.get('mcpRelayUrl');

      if (!relayUrl) {
        setError('Missing mcpRelayUrl parameter in URL.');
        return;
      }

      try {
        const host = new URL(relayUrl).hostname;
        if (host !== '127.0.0.1' && host !== '[::1]') {
          setError(`Front Desk local mode only allows loopback connections (127.0.0.1 or [::1]). Received host: ${host}`);
          return;
        }
      } catch (e) {
        setError(`Invalid mcpRelayUrl parameter in URL: ${relayUrl}. ${e}`);
        return;
      }

      setStatus({
        type: 'connecting',
        message: `"${clientInfo}" is ready to connect to Front Desk Browser Use.`
      });

      const parsedVersion = parseInt(params.get('protocolVersion') ?? '', 10);
      const requestedVersion = isNaN(parsedVersion) ? 1 : parsedVersion;
      if (requestedVersion > SUPPORTED_PROTOCOL_VERSION) {
        const extensionVersion = chrome.runtime.getManifest().version;
        setStatus({
          type: 'error',
          versionMismatch: {
            extensionVersion,
          }
        });
        return;
      }
      if (requestedVersion < SUPPORTED_PROTOCOL_VERSION) {
        setError('The client uses an unsupported protocol version. Update Playwright MCP or CLI to the latest version.');
        return;
      }
      // The background only records the relay URL; the WS to the relay opens
      // once the user clicks Allow.
      await chrome.runtime.sendMessage({ type: 'connectionRequested', mcpRelayUrl: relayUrl });

      const expectedToken = getOrCreateAuthToken();
      const token = params.get('token');
      if (token === expectedToken) {
        await handleConnectToTab();
        return;
      }
      if (token) {
        setError('Invalid token provided.');
        return;
      }

    };
    void runAsync();
  }, []);

  const handleConnectToTab = useCallback(async () => {
    try {
      const response = await chrome.runtime.sendMessage({
        type: 'connectToTab',
        clientName: clientInfo,
      });

      if (response?.success) {
        setStatus({ type: 'connected', message: `"${clientInfo}" connected.` });
      } else {
        setStatus({
          type: 'error',
          message: response?.error || `"${clientInfo}" failed to connect.`
        });
      }
    } catch (e) {
      setStatus({
        type: 'error',
        message: `"${clientInfo}" failed to connect: ${e}`
      });
    }
  }, []);

  return (
    <div className='app-container'>
      <div className='content-wrapper'>
        {status && (
          <div className='status-container'>
            <StatusBanner status={status} />
          </div>
        )}

        {status?.type === 'connecting' && (
          <div className='warning-banner'>
            Front Desk will connect to every normal Chrome tab and automatically include tabs opened later.
          </div>
        )}

        {status?.type === 'connecting' && (
          <AuthTokenSection />
        )}

        {status?.type === 'connecting' && (
          <Button variant='primary' onClick={() => handleConnectToTab()}>
            Connect Front Desk
          </Button>
        )}
      </div>
    </div>
  );
};

const VersionMismatchError: React.FC<{ extensionVersion: string }> = ({ extensionVersion }) => {
  const readmeUrl = 'https://github.com/microsoft/playwright/blob/main/packages/extension/README.md';
  return (
    <div>
      The local Playwright client requires a newer Front Desk extension version (current version: {extensionVersion}).{' '}
      Rebuild and reload the unpacked extension.{' '}
      See <a href={readmeUrl} target='_blank' rel='noopener noreferrer'>installation instructions</a> for more details.
    </div>
  );
};

const StatusBanner: React.FC<{ status: Status }> = ({ status }) => {
  return (
    <div className={`status-banner ${status.type}`}>
      {'versionMismatch' in status ? (
        <VersionMismatchError
          extensionVersion={status.versionMismatch.extensionVersion}
        />
      ) : (
        status.message
      )}
    </div>
  );
};

// Initialize the React app
const container = document.getElementById('root');
if (container) {
  const root = createRoot(container);
  root.render(<ConnectApp />);
}
