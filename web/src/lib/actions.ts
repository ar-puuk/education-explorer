/** Move keyboard focus into a dialog when it opens and return it to the opener when it closes. */
export function focusDialog(node: HTMLElement) {
  const opener = document.activeElement as HTMLElement | null
  node.setAttribute('tabindex', '-1')
  node.focus()
  return {
    destroy() {
      opener?.focus?.()
    },
  }
}
