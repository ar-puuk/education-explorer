// One themed tooltip for everything that is not an Observable Plot mark (those use Plot's own tip).
// Native `title` tooltips are slow, unthemed, never appear on touch, and are ignored over small or scrolling targets,
// so strips, bars and KPIs use this instead. Usage: <td use:tooltip={'text'}>.
let el: HTMLDivElement | null = null
let owner: HTMLElement | null = null
let hideTimer: ReturnType<typeof setTimeout> | undefined

function box(): HTMLDivElement {
  if (!el) {
    // a tap anywhere else dismisses a touch tooltip
    document.addEventListener('pointerdown', (e) => {
      if (owner && !owner.contains(e.target as Node)) hide(owner)
    })
    el = document.createElement('div')
    el.className = 'ee-tip'
    el.setAttribute('role', 'tooltip')
    el.id = 'ee-tip'
    document.body.appendChild(el)
  }
  return el
}

function place(x: number, y: number) {
  const t = box()
  const pad = 12
  const w = t.offsetWidth
  const h = t.offsetHeight
  let left = x + pad
  let top = y + pad + 6
  if (left + w > window.innerWidth - 8) left = Math.max(8, x - w - pad)
  if (top + h > window.innerHeight - 8) top = Math.max(8, y - h - pad)
  t.style.left = `${left}px`
  t.style.top = `${top}px`
}

function show(node: HTMLElement, text: string, x: number, y: number) {
  clearTimeout(hideTimer)
  const t = box()
  owner = node
  t.textContent = text
  t.dataset.show = '1'
  node.setAttribute('aria-describedby', 'ee-tip')
  place(x, y)
}

function hide(node: HTMLElement) {
  if (owner !== node) return
  owner = null
  node.removeAttribute('aria-describedby')
  if (el) delete el.dataset.show
}

export function tooltip(node: HTMLElement, initial: string | null | undefined) {
  let text = initial ?? ''
  const at = (e: PointerEvent) => text && show(node, text, e.clientX, e.clientY)
  const move = (e: PointerEvent) => owner === node && place(e.clientX, e.clientY)
  // a touch tap ends with pointerleave straight away, so touch tooltips stay until a timer or the next tap elsewhere
  const leave = (e: PointerEvent) => {
    if (e.pointerType !== 'touch') hide(node)
  }
  const touch = (e: PointerEvent) => {
    if (e.pointerType !== 'touch') return
    at(e)
    clearTimeout(hideTimer)
    hideTimer = setTimeout(() => hide(node), 2600)
  }
  const blur = () => hide(node)
  const focus = () => {
    if (!text) return
    const r = node.getBoundingClientRect()
    show(node, text, r.left + r.width / 2, r.bottom)
  }
  node.addEventListener('pointerenter', at)
  node.addEventListener('pointermove', move)
  node.addEventListener('pointerleave', leave)
  node.addEventListener('pointerdown', touch)
  node.addEventListener('focus', focus)
  node.addEventListener('blur', blur)
  return {
    update(next: string | null | undefined) {
      text = next ?? ''
      if (owner === node && el) el.textContent = text
    },
    destroy() {
      hide(node)
      node.removeEventListener('pointerenter', at)
      node.removeEventListener('pointermove', move)
      node.removeEventListener('pointerleave', leave)
      node.removeEventListener('pointerdown', touch)
      node.removeEventListener('focus', focus)
      node.removeEventListener('blur', blur)
    },
  }
}

/** Show the tooltip for something that does not use the action (for example a position along a track). */
export const showTip = (node: HTMLElement, text: string, x: number, y: number) => show(node, text, x, y)
export const hideTip = (node: HTMLElement) => hide(node)
