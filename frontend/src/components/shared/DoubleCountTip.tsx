import { InfoTip } from './InfoTip';
import { money } from '../../utils/format';

interface Props {
  correction: number;
  reported?: number;
}

// Explains the correction for Pelotonia's double-counted team funds. Renders
// nothing when no correction is active, so it disappears on its own once
// Pelotonia's totals are clean again.
export function DoubleCountTip({ correction, reported }: Props) {
  if (!(correction > 0)) return null;
  return (
    <InfoTip label="Why this total differs from pelotonia.org">
      <p>
        <strong>Why this is lower than pelotonia.org.</strong> Since mid-October 2026,
        Pelotonia's site counts some team money twice. When a captain assigns team funds to a
        rider, the money stays in the team's general funds and is added again through the
        rider's credit.
      </p>
      <p>
        This dashboard subtracts the assigned amount, {money(correction)}
        {reported ? ` (pelotonia.org shows ${money(reported)})` : ''}. If Pelotonia fixes its
        totals, the dashboard detects it and goes back to their figures automatically.
      </p>
    </InfoTip>
  );
}
