import styles from '../../styles/table.module.css';

interface BadgeTagProps {
  tags: string;
  isFirstYear?: boolean;
  isSurvivor?: boolean;
  isCaptain?: boolean;
  isHighRoller?: boolean;
}

export function BadgeTag({ tags, isFirstYear, isSurvivor, isCaptain, isHighRoller }: BadgeTagProps) {
  const badges: { text: string; className: string }[] = [];

  if (isHighRoller) {
    badges.push({ text: 'High Roller', className: styles.badgeHr });
  }

  if (isSurvivor) {
    badges.push({ text: 'Survivor', className: styles.badgeSurvivor });
  }

  if (isFirstYear) {
    badges.push({ text: '1st Year', className: styles.badgeFirstYear });
  }

  if (isCaptain) {
    badges.push({ text: 'Captain', className: styles.badgeTag });
  }

  // Parse additional tags from JSON string
  if (tags) {
    try {
      const parsed: string[] = JSON.parse(tags);
      for (const tag of parsed) {
        // Avoid duplicating badges already added above
        const lower = tag.toLowerCase();
        if (
          lower.includes('high roller') ||
          lower.includes('survivor') ||
          lower.includes('1st year') ||
          lower.includes('first year') ||
          lower.includes('captain')
        ) {
          continue;
        }
        badges.push({ text: tag, className: styles.badgeTag });
      }
    } catch {
      // tags might not be valid JSON; treat as single tag
      if (tags.trim()) {
        badges.push({ text: tags, className: styles.badgeTag });
      }
    }
  }

  if (badges.length === 0) return null;

  return (
    <>
      {badges.map((b, i) => (
        <span key={i} className={b.className}>
          {b.text}
        </span>
      ))}
    </>
  );
}
