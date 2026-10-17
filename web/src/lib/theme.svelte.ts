export type ThemePref = 'system' | 'light' | 'dark'

function load(): ThemePref {
  try {
    const t = localStorage.getItem('theme')
    if (t === 'light' || t === 'dark' || t === 'system') return t
  } catch {
    /* storage unavailable: fall back to system */
  }
  return 'system'
}

const mq = typeof matchMedia === 'function' ? matchMedia('(prefers-color-scheme: dark)') : null
const initial = load()
let pref = $state<ThemePref>(initial)
let systemDark = $state(mq?.matches ?? false)
mq?.addEventListener('change', (e) => (systemDark = e.matches))

function apply(p: ThemePref) {
  if (p === 'system') delete document.documentElement.dataset.theme
  else document.documentElement.dataset.theme = p
}
apply(initial)

export const theme = {
  get pref() {
    return pref
  },
  set pref(v: ThemePref) {
    pref = v
    apply(v)
    try {
      localStorage.setItem('theme', v)
    } catch {
      /* ignore */
    }
  },
  get effective(): 'light' | 'dark' {
    return pref === 'system' ? (systemDark ? 'dark' : 'light') : pref
  },
}
