import { beforeEach, describe, expect, it, vi } from 'vitest';
import { portfolioApi } from '../portfolio';

const { post } = vi.hoisted(() => ({
  post: vi.fn(),
}));

vi.mock('../index', () => ({
  default: {
    post,
  },
}));

describe('portfolioApi', () => {
  beforeEach(() => {
    post.mockReset();
  });

  it('uses a long timeout for vision-backed screenshot imports', async () => {
    post.mockResolvedValueOnce({
      data: {
        suggested_account_name: 'GF',
        broker_hint: 'gf',
        positions: [],
        record_count: 0,
      },
    });

    const file = new File(['fake'], 'position.png', { type: 'image/png' });
    await portfolioApi.parseScreenshotImport(file, {
      accountId: 2,
      brokerHint: 'gf',
      screenshotDate: '2026-07-03',
    });

    expect(post).toHaveBeenCalledWith(
      '/api/v1/portfolio/imports/screenshot/parse',
      expect.any(FormData),
      {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 180000,
      },
    );
  });
});
