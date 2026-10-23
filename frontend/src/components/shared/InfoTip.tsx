import { useCallback, useEffect, useId, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { createPortal } from 'react-dom';
import styles from '../../styles/infotip.module.css';

interface Props {
  label: string;
  children: ReactNode;
}

const WIDTH = 300;

// A small "i" button with an explanation. It opens on hover, keyboard focus or
// tap, and closes on leave, blur, Escape or a tap elsewhere. The popover is portaled to <body> with fixed
// positioning, so flip cards and overflow:hidden parents can't clip it.
export function InfoTip({ label, children }: Props) {
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState({ top: 0, left: 0 });
  const btn = useRef<HTMLButtonElement>(null);
  const id = useId();

  const place = useCallback(() => {
    const r = btn.current?.getBoundingClientRect();
    if (!r) return;
    const left = Math.min(Math.max(8, r.left + r.width / 2 - WIDTH / 2), window.innerWidth - WIDTH - 8);
    setPos({ top: r.bottom + 8, left });
  }, []);

  const show = useCallback(() => {
    place();
    setOpen(true);
  }, [place]);

  useEffect(() => {
    if (!open) return;
    const close = (e: Event) => {
      if (e instanceof KeyboardEvent && e.key !== 'Escape') return;
      if (e instanceof MouseEvent && btn.current?.contains(e.target as Node)) return;
      setOpen(false);
    };
    document.addEventListener('keydown', close);
    document.addEventListener('mousedown', close);
    window.addEventListener('scroll', place, true);
    return () => {
      document.removeEventListener('keydown', close);
      document.removeEventListener('mousedown', close);
      window.removeEventListener('scroll', place, true);
    };
  }, [open, place]);

  return (
    <>
      <button
        ref={btn}
        type="button"
        className={styles.button}
        aria-label={label}
        aria-describedby={open ? id : undefined}
        onClick={(e) => {
          // Open only: on touch screens a tap fires mouseenter then click, so a
          // toggle would close it at once. Tapping elsewhere closes it.
          e.stopPropagation();
          show();
        }}
        onMouseEnter={show}
        onMouseLeave={() => setOpen(false)}
        onFocus={show}
        onBlur={() => setOpen(false)}
      >
        i
      </button>
      {open &&
        createPortal(
          <div id={id} role="tooltip" className={styles.popover} style={{ top: pos.top, left: pos.left, width: WIDTH }}>
            {children}
          </div>,
          document.body,
        )}
    </>
  );
}
