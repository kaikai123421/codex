import type React from 'react';
import type { ParsedApiError } from '../../api/error';
import { useUiLanguage } from '../../contexts/UiLanguageContext';

interface ApiErrorAlertProps {
  error: ParsedApiError;
  className?: string;
  actionLabel?: string;
  onAction?: () => void;
  dismissLabel?: string;
  onDismiss?: () => void;
}

const MAX_DETAIL_LENGTH = 1800;

function stripHtmlTags(value: string): string {
  return value
    .replace(/<script[\s\S]*?<\/script>/gi, ' ')
    .replace(/<style[\s\S]*?<\/style>/gi, ' ')
    .replace(/<[^>]+>/g, ' ')
    .replace(/&nbsp;/gi, ' ')
    .replace(/&lt;/gi, '<')
    .replace(/&gt;/gi, '>')
    .replace(/&amp;/gi, '&')
    .replace(/\s+/g, ' ')
    .trim();
}

function summarizeHtmlError(rawMessage: string): string | null {
  const trimmed = rawMessage.trim();
  const probe = trimmed.slice(0, 4096).toLowerCase();
  const looksLikeHtml = (
    probe.startsWith('<!doctype')
    || probe.startsWith('<html')
    || probe.includes('<html')
    || probe.includes('<title>502</title>')
    || probe.includes('<body')
  );

  if (!looksLikeHtml) {
    return null;
  }

  const title = trimmed.match(/<title[^>]*>([\s\S]*?)<\/title>/i)?.[1];
  const titleText = title ? stripHtmlTags(title) : '';
  const statusLine = titleText ? `上游返回 HTML 错误页：${titleText}` : '上游返回 HTML 错误页。';

  return [
    statusLine,
    '已隐藏原始网页源码，避免把 Render 或上游网关的整页 HTML 展示出来。',
    '建议：稍后重试；如果持续出现，请检查 Render 日志、模型 API Key、行情源、代理/DNS 与服务健康检查。',
  ].join('\n');
}

function getSafeDetails(rawMessage: string): string {
  const trimmed = rawMessage.trim();
  const htmlSummary = summarizeHtmlError(trimmed);
  if (htmlSummary) {
    return htmlSummary;
  }

  if (trimmed.length <= MAX_DETAIL_LENGTH) {
    return trimmed;
  }

  return `${trimmed.slice(0, MAX_DETAIL_LENGTH)}\n\n... 已截断 ${trimmed.length - MAX_DETAIL_LENGTH} 个字符`;
}

export const ApiErrorAlert: React.FC<ApiErrorAlertProps> = ({
  error,
  className = '',
  actionLabel,
  onAction,
  dismissLabel,
  onDismiss,
}) => {
  const { t } = useUiLanguage();
  const details = getSafeDetails(error.rawMessage);
  const showDetails = Boolean(details && details !== error.message.trim());

  return (
    <div
      className={`rounded-xl border border-[hsl(var(--color-danger-alert-border)/0.3)] bg-[hsl(var(--color-danger-alert-bg)/0.1)] px-4 py-3 text-[hsl(var(--color-danger-alert-text))] ${className}`}
      role="alert"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm font-semibold">{error.title}</p>
          <p className="mt-1 text-xs opacity-90">{error.message}</p>
        </div>
        {onDismiss ? (
          <button
            type="button"
            className="shrink-0 rounded-md border border-[hsl(var(--color-danger-alert-border)/0.3)] bg-[hsl(var(--color-danger-alert-bg)/0.1)] px-2 py-1 text-[11px] text-[hsl(var(--color-danger-alert-text))] transition hover:bg-[hsl(var(--color-danger-alert-bg)/0.15)]"
            onClick={onDismiss}
          >
            {dismissLabel ?? t('common.close')}
          </button>
        ) : null}
      </div>
      {showDetails ? (
        <details className="mt-3 rounded-lg border border-subtle bg-surface-2 px-3 py-2">
          <summary className="cursor-pointer text-xs text-[hsl(var(--color-danger-alert-text))] opacity-90">{t('common.details')}</summary>
          <pre className="mt-2 whitespace-pre-wrap break-words text-[11px] leading-5 text-[hsl(var(--color-danger-alert-text))] opacity-85">
            {details}
          </pre>
        </details>
      ) : null}
      {actionLabel && onAction ? (
        <button
          type="button"
          className="mt-3 inline-flex items-center justify-center rounded-md border border-[hsl(var(--color-danger-alert-border)/0.3)] bg-[hsl(var(--color-danger-alert-bg)/0.1)] px-3 py-1.5 text-xs font-medium text-[hsl(var(--color-danger-alert-text))] transition hover:bg-[hsl(var(--color-danger-alert-bg)/0.15)]"
          onClick={onAction}
        >
          {actionLabel}
        </button>
      ) : null}
    </div>
  );
};
