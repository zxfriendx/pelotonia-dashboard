import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { Pagination } from '../../src/components/shared/Pagination';

describe('Pagination', () => {
  it('shows page X of Y', () => {
    render(
      <Pagination page={2} totalPages={5} pageSize={10} setPage={() => {}} setPageSize={() => {}} />,
    );
    expect(screen.getByText('Page 2 of 5')).toBeInTheDocument();
  });

  it('prev button is disabled on page 1', () => {
    render(
      <Pagination page={1} totalPages={5} pageSize={10} setPage={() => {}} setPageSize={() => {}} />,
    );
    const prevBtn = screen.getByText(/Prev/);
    expect(prevBtn).toBeDisabled();
  });

  it('next button is disabled on last page', () => {
    render(
      <Pagination page={5} totalPages={5} pageSize={10} setPage={() => {}} setPageSize={() => {}} />,
    );
    const nextBtn = screen.getByText(/Next/);
    expect(nextBtn).toBeDisabled();
  });

  it('prev and next are enabled on a middle page', () => {
    render(
      <Pagination page={3} totalPages={5} pageSize={10} setPage={() => {}} setPageSize={() => {}} />,
    );
    expect(screen.getByText(/Prev/)).not.toBeDisabled();
    expect(screen.getByText(/Next/)).not.toBeDisabled();
  });

  it('clicking next calls setPage with page + 1', () => {
    const setPage = vi.fn();
    render(
      <Pagination page={2} totalPages={5} pageSize={10} setPage={setPage} setPageSize={() => {}} />,
    );
    fireEvent.click(screen.getByText(/Next/));
    expect(setPage).toHaveBeenCalledWith(3);
  });

  it('clicking prev calls setPage with page - 1', () => {
    const setPage = vi.fn();
    render(
      <Pagination page={3} totalPages={5} pageSize={10} setPage={setPage} setPageSize={() => {}} />,
    );
    fireEvent.click(screen.getByText(/Prev/));
    expect(setPage).toHaveBeenCalledWith(2);
  });

  it('changing page size calls setPageSize', () => {
    const setPageSize = vi.fn();
    render(
      <Pagination page={1} totalPages={5} pageSize={10} setPage={() => {}} setPageSize={setPageSize} />,
    );
    const select = screen.getByDisplayValue('10');
    fireEvent.change(select, { target: { value: '25' } });
    expect(setPageSize).toHaveBeenCalledWith(25);
  });
});
