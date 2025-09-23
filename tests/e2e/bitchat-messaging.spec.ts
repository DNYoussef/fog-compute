import { test, expect, Page } from '@playwright/test';

/**
 * Bitchat P2P Messaging E2E Tests
 * Tests peer-to-peer messaging, encryption, and real-time communication
 */

test.describe('Bitchat P2P Messaging', () => {
  let page: Page;
  let secondPage: Page;

  test.beforeAll(async ({ browser }) => {
    page = await browser.newPage();
    secondPage = await browser.newPage();
  });

  test.afterAll(async () => {
    await page.close();
    await secondPage.close();
  });

  test('Complete P2P messaging workflow', async () => {
    // Setup two peers
    await test.step('Initialize first peer', async () => {
      await page.goto('/bitchat');
      await expect(page).toHaveTitle(/Bitchat/i);

      const chat = page.locator('[data-testid="bitchat-container"]');
      await expect(chat).toBeVisible({ timeout: 10000 });

      // Set peer identity
      await page.fill('[data-testid="peer-name-input"]', 'Peer-1');
      await page.click('[data-testid="join-network-button"]');

      await expect(page.locator('[data-testid="peer-status"]')).toHaveText('Connected', { timeout: 10000 });
    });

    await test.step('Initialize second peer', async () => {
      await secondPage.goto('/bitchat');

      const chat = secondPage.locator('[data-testid="bitchat-container"]');
      await expect(chat).toBeVisible({ timeout: 10000 });

      await secondPage.fill('[data-testid="peer-name-input"]', 'Peer-2');
      await secondPage.click('[data-testid="join-network-button"]');

      await expect(secondPage.locator('[data-testid="peer-status"]')).toHaveText('Connected', { timeout: 10000 });
    });

    // Verify peer discovery
    await test.step('Discover peers', async () => {
      await page.waitForTimeout(2000); // Allow for peer discovery

      const peerList = page.locator('[data-testid="peer-list"]');
      await expect(peerList).toBeVisible();

      const peer2 = page.locator('[data-testid="peer-item"]', { hasText: 'Peer-2' });
      await expect(peer2).toBeVisible({ timeout: 15000 });
    });

    // Send and receive messages
    await test.step('Send P2P message', async () => {
      // Peer-1 selects Peer-2
      await page.click('[data-testid="peer-item"]:has-text("Peer-2")');

      const messageInput = page.locator('[data-testid="message-input"]');
      await expect(messageInput).toBeVisible();

      await messageInput.fill('Hello from Peer-1!');
      await page.click('[data-testid="send-message-button"]');

      // Verify message appears in sender's chat
      const sentMessage = page.locator('[data-testid="message-bubble"]:has-text("Hello from Peer-1!")');
      await expect(sentMessage).toBeVisible();
      await expect(sentMessage).toHaveClass(/sent/);
    });

    await test.step('Receive P2P message', async () => {
      // Peer-2 should receive the message
      const receivedMessage = secondPage.locator('[data-testid="message-bubble"]:has-text("Hello from Peer-1!")');
      await expect(receivedMessage).toBeVisible({ timeout: 10000 });
      await expect(receivedMessage).toHaveClass(/received/);

      // Check notification
      const notification = secondPage.locator('[data-testid="new-message-notification"]');
      await expect(notification).toBeVisible();
    });

    await test.step('Reply to message', async () => {
      // Peer-2 replies
      await secondPage.click('[data-testid="peer-item"]:has-text("Peer-1")');

      const messageInput = secondPage.locator('[data-testid="message-input"]');
      await messageInput.fill('Hi Peer-1! Message received.');
      await secondPage.click('[data-testid="send-message-button"]');

      // Verify on both sides
      await expect(secondPage.locator('[data-testid="message-bubble"]:has-text("Hi Peer-1!")').last()).toBeVisible();
      await expect(page.locator('[data-testid="message-bubble"]:has-text("Hi Peer-1!")').last()).toBeVisible({ timeout: 10000 });
    });

    await test.step('Verify message encryption', async () => {
      // Check encryption indicator
      const encryptionBadge = page.locator('[data-testid="encryption-badge"]');
      await expect(encryptionBadge).toBeVisible();
      await expect(encryptionBadge).toContainText(/Encrypted|E2E/i);

      // Verify encryption details
      await encryptionBadge.click();
      const encryptionInfo = page.locator('[data-testid="encryption-info"]');
      await expect(encryptionInfo).toBeVisible();
      await expect(encryptionInfo).toContainText(/AES|RSA|End-to-End/i);
    });
  });

  test('Group messaging and channels', async () => {
    await test.step('Create group chat', async () => {
      await page.goto('/bitchat');
      await page.fill('[data-testid="peer-name-input"]', 'Group-Admin');
      await page.click('[data-testid="join-network-button"]');

      await page.click('[data-testid="create-group-button"]');

      await page.fill('[data-testid="group-name-input"]', 'Test Group');
      await page.fill('[data-testid="group-description-input"]', 'E2E test group chat');

      // Add members
      await page.click('[data-testid="add-members-button"]');
      await page.check('[data-testid="peer-checkbox"]:first-child');
      await page.check('[data-testid="peer-checkbox"]:nth-child(2)');

      await page.click('[data-testid="create-group-confirm-button"]');

      await expect(page.locator('[data-testid="group-item"]', { hasText: 'Test Group' })).toBeVisible();
    });

    await test.step('Send group message', async () => {
      await page.click('[data-testid="group-item"]:has-text("Test Group")');

      const messageInput = page.locator('[data-testid="message-input"]');
      await messageInput.fill('Hello everyone in the group!');
      await page.click('[data-testid="send-message-button"]');

      // Verify message in group chat
      const groupMessage = page.locator('[data-testid="message-bubble"]:has-text("Hello everyone")');
      await expect(groupMessage).toBeVisible();
    });

    await test.step('Verify group member delivery', async () => {
      // Check delivery status
      const deliveryStatus = page.locator('[data-testid="delivery-status"]').last();
      await expect(deliveryStatus).toContainText(/Delivered|Sent/i, { timeout: 10000 });

      // Check read receipts
      await page.waitForTimeout(2000);
      const readReceipts = page.locator('[data-testid="read-receipt"]').last();
      const receiptText = await readReceipts.textContent();
      expect(receiptText).toMatch(/\d+/); // Should show number of readers
    });
  });

  test('File sharing over P2P', async () => {
    await test.step('Setup peer connection', async () => {
      await page.goto('/bitchat');
      await page.fill('[data-testid="peer-name-input"]', 'File-Sender');
      await page.click('[data-testid="join-network-button"]');

      await secondPage.goto('/bitchat');
      await secondPage.fill('[data-testid="peer-name-input"]', 'File-Receiver');
      await secondPage.click('[data-testid="join-network-button"]');

      // Wait for peer discovery
      await page.waitForTimeout(3000);
      await page.click('[data-testid="peer-item"]:has-text("File-Receiver")');
    });

    await test.step('Send file', async () => {
      await page.click('[data-testid="attach-file-button"]');

      // Upload file
      const fileInput = page.locator('[data-testid="file-input"]');
      await fileInput.setInputFiles({
        name: 'test-file.txt',
        mimeType: 'text/plain',
        buffer: Buffer.from('This is a test file content')
      });

      await page.click('[data-testid="send-file-button"]');

      // Verify file appears in chat
      const fileMessage = page.locator('[data-testid="file-message"]', { hasText: 'test-file.txt' });
      await expect(fileMessage).toBeVisible();

      // Check upload progress
      const progressBar = page.locator('[data-testid="upload-progress"]');
      await expect(progressBar).toBeVisible();
      await expect(progressBar).toHaveAttribute('value', '100', { timeout: 15000 });
    });

    await test.step('Receive and download file', async () => {
      // File receiver should see the file
      const receivedFile = secondPage.locator('[data-testid="file-message"]', { hasText: 'test-file.txt' });
      await expect(receivedFile).toBeVisible({ timeout: 15000 });

      // Verify file metadata
      await expect(receivedFile.locator('[data-testid="file-size"]')).toBeVisible();
      await expect(receivedFile.locator('[data-testid="file-type"]')).toContainText('text/plain');

      // Download file
      const downloadButton = receivedFile.locator('[data-testid="download-file-button"]');
      await expect(downloadButton).toBeVisible();

      const [download] = await Promise.all([
        secondPage.waitForEvent('download'),
        downloadButton.click()
      ]);

      expect(download.suggestedFilename()).toBe('test-file.txt');
    });
  });

  test('Voice and video calls (WebRTC)', async () => {
    await test.step('Initiate voice call', async () => {
      await page.goto('/bitchat');
      await page.fill('[data-testid="peer-name-input"]', 'Caller');
      await page.click('[data-testid="join-network-button"]');

      await page.waitForTimeout(2000);
      await page.click('[data-testid="peer-item"]').first();

      // Start voice call
      await page.click('[data-testid="voice-call-button"]');

      // Verify call UI
      const callInterface = page.locator('[data-testid="call-interface"]');
      await expect(callInterface).toBeVisible();

      await expect(page.locator('[data-testid="call-status"]')).toHaveText('Calling...', { timeout: 5000 });
    });

    await test.step('Accept call on peer', async () => {
      await secondPage.goto('/bitchat');
      await secondPage.fill('[data-testid="peer-name-input"]', 'Receiver');
      await secondPage.click('[data-testid="join-network-button"]');

      // Incoming call notification
      const incomingCall = secondPage.locator('[data-testid="incoming-call-notification"]');
      await expect(incomingCall).toBeVisible({ timeout: 10000 });

      await secondPage.click('[data-testid="accept-call-button"]');

      // Verify call connected
      await expect(secondPage.locator('[data-testid="call-status"]')).toHaveText('Connected', { timeout: 10000 });
    });

    await test.step('Verify call controls', async () => {
      // Check audio controls
      await expect(page.locator('[data-testid="mute-button"]')).toBeVisible();
      await expect(page.locator('[data-testid="volume-control"]')).toBeVisible();
      await expect(page.locator('[data-testid="end-call-button"]')).toBeVisible();

      // Test mute
      await page.click('[data-testid="mute-button"]');
      await expect(page.locator('[data-testid="mute-status"]')).toHaveText('Muted');
    });

    await test.step('End call', async () => {
      await page.click('[data-testid="end-call-button"]');

      await expect(page.locator('[data-testid="call-interface"]')).not.toBeVisible();
      await expect(secondPage.locator('[data-testid="call-interface"]')).not.toBeVisible({ timeout: 5000 });
    });
  });

  test('Message search and history', async () => {
    await test.step('Send multiple messages', async () => {
      await page.goto('/bitchat');
      await page.fill('[data-testid="peer-name-input"]', 'Searcher');
      await page.click('[data-testid="join-network-button"]');

      await page.waitForTimeout(2000);
      await page.click('[data-testid="peer-item"]').first();

      // Send various messages
      const messages = [
        'This is the first test message',
        'Second message about testing',
        'Third message with keyword: important',
        'Fourth regular message',
        'Fifth message also important'
      ];

      for (const msg of messages) {
        await page.fill('[data-testid="message-input"]', msg);
        await page.click('[data-testid="send-message-button"]');
        await page.waitForTimeout(500);
      }
    });

    await test.step('Search messages', async () => {
      await page.click('[data-testid="search-messages-button"]');

      const searchInput = page.locator('[data-testid="message-search-input"]');
      await searchInput.fill('important');

      // Verify search results
      const searchResults = page.locator('[data-testid="search-result"]');
      await expect(searchResults).toHaveCount(2);

      await expect(searchResults.first()).toContainText('important');
    });

    await test.step('Navigate message history', async () => {
      await page.click('[data-testid="message-history-button"]');

      const historyPanel = page.locator('[data-testid="message-history-panel"]');
      await expect(historyPanel).toBeVisible();

      // Filter by date
      await page.click('[data-testid="date-filter-button"]');
      await page.selectOption('[data-testid="date-range-select"]', 'today');

      const messages = page.locator('[data-testid="history-message"]');
      await expect(messages.count()).resolves.toBeGreaterThan(0);
    });

    await test.step('Export chat history', async () => {
      await page.click('[data-testid="export-chat-button"]');

      await page.selectOption('[data-testid="export-format-select"]', 'json');

      const [download] = await Promise.all([
        page.waitForEvent('download'),
        page.click('[data-testid="confirm-export-button"]')
      ]);

      expect(download.suggestedFilename()).toMatch(/chat.*\.json$/);
    });
  });

  test('Status and presence', async () => {
    await test.step('Set user status', async () => {
      await page.goto('/bitchat');
      await page.fill('[data-testid="peer-name-input"]', 'Status-User');
      await page.click('[data-testid="join-network-button"]');

      await page.click('[data-testid="status-dropdown"]');

      // Set status to busy
      await page.click('[data-testid="status-busy"]');

      await expect(page.locator('[data-testid="current-status"]')).toContainText('Busy');
    });

    await test.step('Verify status visibility', async () => {
      await secondPage.goto('/bitchat');
      await secondPage.fill('[data-testid="peer-name-input"]', 'Observer');
      await secondPage.click('[data-testid="join-network-button"]');

      await secondPage.waitForTimeout(3000);

      // Check peer's status
      const peerStatus = secondPage.locator('[data-testid="peer-item"]:has-text("Status-User") [data-testid="peer-status-badge"]');
      await expect(peerStatus).toContainText('Busy', { timeout: 10000 });
    });

    await test.step('Set custom status message', async () => {
      await page.click('[data-testid="status-dropdown"]');
      await page.click('[data-testid="custom-status-option"]');

      await page.fill('[data-testid="status-message-input"]', 'In a meeting');
      await page.click('[data-testid="save-status-button"]');

      // Verify custom message
      await expect(page.locator('[data-testid="status-message"]')).toContainText('In a meeting');
    });
  });
});