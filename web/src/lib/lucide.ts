/** Lucide icon nodes (ISC licence), shared by the SVG UI icons and the canvas map markers. */
import {
  Layers, ListFilter, Table2, Columns2, Info, Search, ChevronRight, X, Maximize2, Minimize2, Play, Pause,
  Moon, Sun, Monitor, Plus, Download, GraduationCap, Map, Check, School, House,
} from 'lucide'
import type { IconNode } from 'lucide'

export const UI_ICONS = {
  layers: Layers, filter: ListFilter, table: Table2, compare: Columns2, info: Info, search: Search,
  chev: ChevronRight, x: X, expand: Maximize2, shrink: Minimize2, play: Play, pause: Pause, moon: Moon,
  sun: Sun, monitor: Monitor, plus: Plus, download: Download, cap: GraduationCap, map: Map, check: Check,
} as const satisfies Record<string, IconNode>

export const MARKER_ICONS = { public: School, private: House, college: GraduationCap } as const

/** Build a Path2D (24x24 icon space) from an icon node, for stroking on a canvas. */
export function iconPath2D(node: IconNode): Path2D {
  const p = new Path2D()
  const n = (a: Record<string, string | number | undefined>, k: string) => parseFloat(String(a[k] ?? 0))
  for (const [tag, a] of node) {
    if (tag === 'path') p.addPath(new Path2D(String(a.d)))
    else if (tag === 'circle') p.addPath(new Path2D(`M${n(a, 'cx') + n(a, 'r')} ${n(a, 'cy')}a${n(a, 'r')} ${n(a, 'r')} 0 1 0 ${-2 * n(a, 'r')} 0a${n(a, 'r')} ${n(a, 'r')} 0 1 0 ${2 * n(a, 'r')} 0`))
    else if (tag === 'line') p.addPath(new Path2D(`M${a.x1} ${a.y1}L${a.x2} ${a.y2}`))
    else if (tag === 'polyline' || tag === 'polygon') p.addPath(new Path2D(`M${String(a.points)}${tag === 'polygon' ? 'Z' : ''}`))
    else if (tag === 'rect') {
      const x = n(a, 'x'), y = n(a, 'y'), w = n(a, 'width'), h = n(a, 'height')
      p.addPath(new Path2D(`M${x} ${y}h${w}v${h}h${-w}Z`))
    }
  }
  return p
}
