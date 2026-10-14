/** A small bar chart of counts per year, with a text alternative. */
import type { YearCount } from "@/lib/api/types";

/** Props of {@link Sparkline}. */
export interface SparklineProps {
  /** Counts by year, ascending. */
  data: YearCount[];
  /** What is counted, for the accessible description (e.g. "citations"). */
  label: string;
}

const WIDTH = 160;
const HEIGHT = 36;

/**
 * Bars per year scaled to the largest count; screen readers get the numbers.
 *
 * @returns The chart, or null when there is no data.
 */
export function Sparkline({ data, label }: SparklineProps) {
  if (data.length === 0) return null;
  const max = Math.max(...data.map((item) => item.count), 1);
  const slot = WIDTH / data.length;
  const description = data.map((item) => `${item.year}: ${item.count}`).join(", ");
  return (
    <svg
      className="sparkline"
      width={WIDTH}
      height={HEIGHT}
      viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
      role="img"
      aria-label={`${label} per year: ${description}`}
    >
      {data.map((item, index) => {
        const height = Math.max((item.count / max) * (HEIGHT - 2), item.count > 0 ? 2 : 0);
        return (
          <rect
            key={item.year}
            x={index * slot + 1}
            y={HEIGHT - height}
            width={Math.max(slot - 2, 1)}
            height={height}
            fill="currentColor"
          >
            <title>{`${item.year}: ${item.count}`}</title>
          </rect>
        );
      })}
    </svg>
  );
}
