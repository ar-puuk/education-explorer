/** Runtime marker icons: coloured shape + white glyph. Shape and glyph differ per dataset so
 *  meaning never depends on colour alone. */
export type Dataset = 'public' | 'private' | 'college'
/** What can be selected on the map: a point dataset or a school district polygon. */
export type Selectable = Dataset | 'district'

export const DATASET_LABEL: Record<Dataset, string> = {
  public: 'Public schools (CCD)',
  private: 'Private schools (PSS)',
  college: 'Colleges (IPEDS)',
}

export const SIZE = 28 // logical px

type Ctx = CanvasRenderingContext2D

function shape(ctx: Ctx, kind: Dataset, s: number) {
  const c = s / 2
  ctx.beginPath()
  if (kind === 'public') {
    ctx.arc(c, c, c - 2, 0, Math.PI * 2)
  } else if (kind === 'private') {
    const r = 5
    const a = 2
    const w = s - a * 2
    ctx.roundRect(a, a, w, w, r)
  } else {
    ctx.moveTo(c, 1)
    ctx.lineTo(s - 1, c)
    ctx.lineTo(c, s - 1)
    ctx.lineTo(1, c)
    ctx.closePath()
  }
}

function glyph(ctx: Ctx, kind: Dataset, s: number) {
  const c = s / 2
  ctx.strokeStyle = '#fff'
  ctx.fillStyle = '#fff'
  ctx.lineWidth = 1.8
  ctx.lineJoin = 'round'
  ctx.lineCap = 'round'
  ctx.beginPath()
  if (kind === 'public') {
    // schoolhouse/institution: pediment + columns
    ctx.moveTo(c - 7, c - 2)
    ctx.lineTo(c, c - 7)
    ctx.lineTo(c + 7, c - 2)
    ctx.closePath()
    ctx.fill()
    ctx.fillRect(c - 5.5, c - 0.5, 2, 6)
    ctx.fillRect(c - 1, c - 0.5, 2, 6)
    ctx.fillRect(c + 3.5, c - 0.5, 2, 6)
    ctx.fillRect(c - 7, c + 6, 14, 1.8)
  } else if (kind === 'private') {
    // house
    ctx.moveTo(c - 7, c)
    ctx.lineTo(c, c - 7)
    ctx.lineTo(c + 7, c)
    ctx.moveTo(c - 5, c - 1.5)
    ctx.lineTo(c - 5, c + 6)
    ctx.lineTo(c + 5, c + 6)
    ctx.lineTo(c + 5, c - 1.5)
    ctx.stroke()
    ctx.fillRect(c - 1.5, c + 1.5, 3, 4.5)
  } else {
    // graduation cap
    ctx.moveTo(c - 8, c - 1)
    ctx.lineTo(c, c - 5)
    ctx.lineTo(c + 8, c - 1)
    ctx.lineTo(c, c + 3)
    ctx.closePath()
    ctx.fill()
    ctx.moveTo(c - 4.5, c + 2)
    ctx.lineTo(c - 4.5, c + 6)
    ctx.quadraticCurveTo(c, c + 8.5, c + 4.5, c + 6)
    ctx.lineTo(c + 4.5, c + 2)
    ctx.stroke()
  }
}

export interface IconStyle {
  fill: string
  ring: string
  closed?: boolean
  /** approximate (geocoded) location: dotted outline */
  approx?: boolean
}

export function makeIcon(kind: Dataset, st: IconStyle, ratio = 2): ImageData {
  const px = SIZE * ratio
  const canvas = document.createElement('canvas')
  canvas.width = canvas.height = px
  const ctx = canvas.getContext('2d')!
  ctx.scale(ratio, ratio)
  shape(ctx, kind, SIZE)
  ctx.fillStyle = st.closed ? st.fill + '99' : st.fill
  ctx.fill()
  ctx.lineWidth = 2
  ctx.strokeStyle = st.ring
  if (st.closed) ctx.setLineDash([3, 2])
  else if (st.approx) ctx.setLineDash([1.5, 2.5])
  ctx.stroke()
  ctx.setLineDash([])
  glyph(ctx, kind, SIZE)
  return ctx.getImageData(0, 0, px, px)
}

export function cssVar(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim()
}

/** SVG markup for legend/UI use (same shapes, simplified). */
export function legendSvg(kind: Dataset, size = 18): string {
  const s = size
  const col = `var(--c-${kind})`
  const shapeEl =
    kind === 'public'
      ? `<circle cx="${s / 2}" cy="${s / 2}" r="${s / 2 - 1}" fill="${col}"/>`
      : kind === 'private'
        ? `<rect x="1" y="1" width="${s - 2}" height="${s - 2}" rx="3" fill="${col}"/>`
        : `<polygon points="${s / 2},0.5 ${s - 0.5},${s / 2} ${s / 2},${s - 0.5} 0.5,${s / 2}" fill="${col}"/>`
  return `<svg width="${s}" height="${s}" viewBox="0 0 ${s} ${s}" aria-hidden="true">${shapeEl}</svg>`
}
