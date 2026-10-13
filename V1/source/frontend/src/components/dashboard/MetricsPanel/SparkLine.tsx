interface SparkLineProps {
  values: number[]
  width?: number
  height?: number
  color?: string
  fillOpacity?: number
}

export function SparkLine({
  values,
  width = 180,
  height = 40,
  color = "var(--accent)",
  fillOpacity = 0.15,
}: SparkLineProps) {
  if (values.length < 2) return null

  const min = Math.min(...values)
  const max = Math.max(...values)
  const range = max - min || 1

  const pad = 2
  const w = width - pad * 2
  const h = height - pad * 2

  const points = values.map((v, i) => ({
    x: pad + (i / (values.length - 1)) * w,
    y: pad + (1 - (v - min) / range) * h,
  }))

  const linePath = points
    .map((p, i) => `${i === 0 ? "M" : "L"}${p.x.toFixed(1)},${p.y.toFixed(1)}`)
    .join(" ")

  const fillPath =
    linePath +
    ` L${points[points.length - 1]!.x.toFixed(1)},${(pad + h).toFixed(1)}` +
    ` L${points[0]!.x.toFixed(1)},${(pad + h).toFixed(1)} Z`

  const lastPt = points[points.length - 1]!

  return (
    <svg
      width="100%"
      viewBox={`0 0 ${width} ${height}`}
      preserveAspectRatio="none"
      aria-hidden="true"
    >
      <path d={fillPath} fill={color} opacity={fillOpacity} />
      <path d={linePath} fill="none" stroke={color} strokeWidth={1.5} />
      <circle cx={lastPt.x} cy={lastPt.y} r={2.5} fill={color} />
    </svg>
  )
}
