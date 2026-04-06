interface ExportButtonProps {
  onClick: () => void;
  label?: string;
}

export function ExportButton({ onClick, label = '\u2913 CSV' }: ExportButtonProps) {
  return (
    <button className="btn-export" onClick={onClick} title="Export to CSV">
      {label}
    </button>
  );
}
