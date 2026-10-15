import { useEffect, useRef, useState } from "react";
import { money } from "../agents";
import type { Cash } from "../types";

// Checking balance from cash_accounts. When it changes (an approved payment), the number counts
// down to the new value and briefly shows the drop.

export default function CashCard({ cash }: { cash: Cash | null }) {
  const [shown, setShown] = useState(cash?.checking_balance ?? 0);
  const [delta, setDelta] = useState<number | null>(null);
  const prev = useRef<number | null>(null);

  useEffect(() => {
    if (!cash) return;
    const target = cash.checking_balance;
    const from = prev.current ?? target;
    prev.current = target;
    if (from === target) { setShown(target); return; }
    setDelta(target - from);
    const t0 = performance.now();
    let raf = 0;
    const tick = (t: number) => {
      const p = Math.min(1, (t - t0) / 1200);
      setShown(from + (target - from) * (1 - Math.pow(1 - p, 3)));
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    const clear = setTimeout(() => setDelta(null), 4000);
    return () => { cancelAnimationFrame(raf); clearTimeout(clear); };
  }, [cash]);

  return (
    <div className="cash glass">
      <div className="muted">Checking balance</div>
      <div className="cash-big">{cash ? money(shown) : "—"}</div>
      {delta !== null && <div className={`cash-delta ${delta < 0 ? "down" : "up"}`}>{delta < 0 ? "▼" : "▲"} {money(Math.abs(delta))}</div>}
      {cash && <div className="muted small">Free for new spending {money(cash.available_for_new_spending)}</div>}
    </div>
  );
}
