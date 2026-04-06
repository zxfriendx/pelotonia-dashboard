export function money(n: number): string {
  return '$' + Number(n).toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 });
}

export function moneyFull(n: number): string {
  return '$' + Number(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export function moneyShort(n: number): string {
  if (n >= 1_000_000) return '$' + (n / 1_000_000).toFixed(1) + 'M';
  if (n >= 1_000) return '$' + (n / 1_000).toFixed(0) + 'k';
  return '$' + n.toFixed(0);
}

export function shortTeam(name: string | null | undefined): string {
  if (!name) return '—';
  return name.replace('Team Huntington Bank - ', '');
}

export function pct(value: number, goal: number): number {
  if (!goal) return 0;
  return Math.round((value / goal) * 1000) / 10;
}
