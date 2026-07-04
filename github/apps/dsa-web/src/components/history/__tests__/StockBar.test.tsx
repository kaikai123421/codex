import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { StockBar } from '../StockBar';
import type { StockBarItem } from '../../../types/analysis';

const items: StockBarItem[] = [
  {
    id: 1,
    stockCode: 'PORTFOLIO',
    stockName: 'A股持仓组合',
    sentimentScore: 50,
    operationAdvice: '持有',
    analysisCount: 43,
    lastAnalysisTime: '2026-07-03T17:10:00+08:00',
  },
  {
    id: 2,
    stockCode: '515880',
    stockName: '通信ETF国泰',
    analysisCount: 5,
    lastAnalysisTime: '2026-07-03T16:06:00+08:00',
    marketPhaseSummary: {
      market: 'CN',
      phase: 'postmarket',
      warnings: [],
    },
  },
];

describe('StockBar', () => {
  it('keeps destructive bulk controls hidden until manage mode is opened', () => {
    render(
      <StockBar
        items={items}
        isLoading={false}
        selectedRecordId={1}
        onItemClick={vi.fn()}
        onDeleteStock={vi.fn()}
      />,
    );

    expect(screen.getByText('个股栏')).toBeInTheDocument();
    expect(screen.getByText('A股持仓组合')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '管理' })).toBeInTheDocument();
    expect(screen.queryByLabelText('全选当前个股')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '删除' })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '管理' }));

    expect(screen.getByLabelText('全选当前个股')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '删除' })).toBeDisabled();
    expect(screen.getByRole('button', { name: '完成' })).toBeInTheDocument();
  });
});
