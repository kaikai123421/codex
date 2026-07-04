import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { ReportStrategy } from '../ReportStrategy';

describe('ReportStrategy', () => {
  it('renders strategy levels as scannable decision cards', () => {
    render(
      <ReportStrategy
        strategy={{
          idealBuy: '554.9元（MA5上方站稳且放量）',
          secondaryBuy: '553.1元（MA20附近支撑确认）',
          stopLoss: '505.8元（今日最低点，跌破则离场）',
          takeProfit: '580元（前期高点区间）',
        }}
      />,
    );

    expect(screen.getByRole('list', { name: '狙击点位' })).toBeInTheDocument();
    expect(screen.getByRole('listitem', { name: /理想买入点/ })).toHaveTextContent('554.9元');
    expect(screen.getByRole('listitem', { name: /次优买入点/ })).toHaveTextContent('MA20附近支撑确认');
    expect(screen.getByRole('listitem', { name: /止损价位/ })).toHaveTextContent('风险线');
    expect(screen.getByRole('listitem', { name: /止盈目标/ })).toHaveTextContent('目标');
  });
});
