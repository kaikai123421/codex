import { describe, expect, it } from 'vitest';
import { parseApiError } from '../error';

describe('parseApiError', () => {
  it('summarizes HTML gateway errors instead of storing the full page', () => {
    const parsed = parseApiError({
      response: {
        status: 502,
        statusText: 'Bad Gateway',
        data: '<!DOCTYPE html><html><head><title>502</title><style>@font-face{src:url(data:font/woff2;base64,aaaa)}</style></head><body>bad gateway</body></html>',
      },
    });

    expect(parsed.category).toBe('upstream_network');
    expect(parsed.rawMessage).toContain('上游返回 HTML 错误页');
    expect(parsed.rawMessage).toContain('已隐藏原始网页源码');
    expect(parsed.rawMessage).not.toContain('<!DOCTYPE html>');
    expect(parsed.rawMessage).not.toContain('base64');
  });
});
