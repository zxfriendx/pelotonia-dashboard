import styles from '../../styles/table.module.css';
import { MiniBar } from './MiniBar';

interface GoalCellProps {
  value: number;
  goal: number;
}

export function GoalCell({ value, goal }: GoalCellProps) {
  const isOver = goal > 0 && value >= goal;

  return (
    <span className={styles.goalCell}>
      <span className={isOver ? styles.goalOver : styles.goalUnder}>
        {value}
      </span>
      {goal > 0 && (
        <>
          /{goal}
          <MiniBar value={value} max={goal} />
        </>
      )}
    </span>
  );
}
