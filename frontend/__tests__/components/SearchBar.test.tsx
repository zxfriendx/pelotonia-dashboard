import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { SearchBar } from '../../src/components/shared/SearchBar';

describe('SearchBar', () => {
  it('renders with placeholder', () => {
    render(<SearchBar value="" onChange={() => {}} placeholder="Find members..." />);
    expect(screen.getByPlaceholderText('Find members...')).toBeInTheDocument();
  });

  it('renders with default placeholder', () => {
    render(<SearchBar value="" onChange={() => {}} />);
    expect(screen.getByPlaceholderText('Search...')).toBeInTheDocument();
  });

  it('calls onChange on input', () => {
    const onChange = vi.fn();
    render(<SearchBar value="" onChange={onChange} />);
    const input = screen.getByPlaceholderText('Search...');
    fireEvent.change(input, { target: { value: 'alice' } });
    expect(onChange).toHaveBeenCalledWith('alice');
  });

  it('clear button appears when value is non-empty', () => {
    render(<SearchBar value="test" onChange={() => {}} />);
    expect(screen.getByTitle('Clear filter')).toBeInTheDocument();
  });

  it('clear button is absent when value is empty', () => {
    render(<SearchBar value="" onChange={() => {}} />);
    expect(screen.queryByTitle('Clear filter')).not.toBeInTheDocument();
  });

  it('clear button calls onChange with empty string', () => {
    const onChange = vi.fn();
    render(<SearchBar value="test" onChange={onChange} />);
    fireEvent.click(screen.getByTitle('Clear filter'));
    expect(onChange).toHaveBeenCalledWith('');
  });
});
