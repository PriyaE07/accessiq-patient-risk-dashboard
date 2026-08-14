// Minimal inline line icons for the sidebar nav — hand-drawn rather than an
// icon library dependency, since we only need six. All share the same
// stroke-based style (currentColor, so they inherit the nav item's text
// color / active-state color automatically) and viewBox, so they sit
// consistently at any size the CSS gives them.
const ICON_PROPS = {
  viewBox: "0 0 20 20",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.7,
  strokeLinecap: "round",
  strokeLinejoin: "round",
}

export function OverviewIcon() {
  return (
    <svg {...ICON_PROPS}>
      <rect x="2.5" y="2.5" width="6.5" height="6.5" rx="1.3" />
      <rect x="11" y="2.5" width="6.5" height="6.5" rx="1.3" />
      <rect x="2.5" y="11" width="6.5" height="6.5" rx="1.3" />
      <rect x="11" y="11" width="6.5" height="6.5" rx="1.3" />
    </svg>
  )
}

export function CalendarIcon() {
  return (
    <svg {...ICON_PROPS}>
      <rect x="2.5" y="3.5" width="15" height="14" rx="2" />
      <path d="M2.5 7.5h15" />
      <path d="M6 2v3M14 2v3" />
      <path d="M7.5 12.5l2.2 2.2 3-3.4" />
    </svg>
  )
}

export function PulseIcon() {
  return (
    <svg {...ICON_PROPS}>
      <rect x="2.5" y="2.5" width="15" height="15" rx="2.5" />
      <path d="M5 10.5h2.2l1.5-3.5 2 6.5 1.6-3h2.7" />
    </svg>
  )
}

export function ListIcon() {
  return (
    <svg {...ICON_PROPS}>
      <path d="M7 5h10.5M7 10h10.5M7 15h10.5" />
      <circle cx="3" cy="5" r="1" fill="currentColor" stroke="none" />
      <circle cx="3" cy="10" r="1" fill="currentColor" stroke="none" />
      <circle cx="3" cy="15" r="1" fill="currentColor" stroke="none" />
    </svg>
  )
}

export function ClipboardListIcon() {
  return (
    <svg {...ICON_PROPS}>
      <rect x="4" y="3.5" width="12" height="14" rx="1.8" />
      <rect x="7" y="2" width="6" height="3" rx="1" />
      <path d="M7 9.5h6M7 13h6" />
    </svg>
  )
}

export function GaugeIcon() {
  return (
    <svg {...ICON_PROPS}>
      <path d="M3 14a7 7 0 0 1 14 0" />
      <path d="M10 14l3.5-4" />
      <circle cx="10" cy="14" r="1.1" fill="currentColor" stroke="none" />
    </svg>
  )
}

export function BellIcon() {
  return (
    <svg {...ICON_PROPS}>
      <path d="M10 2.8a4.2 4.2 0 0 0-4.2 4.2v2.2c0 .8-.3 1.6-.9 2.2L4 12.5h12l-.9-1.1a3.1 3.1 0 0 1-.9-2.2V7a4.2 4.2 0 0 0-4.2-4.2z" />
      <path d="M8.2 15.3a1.8 1.8 0 0 0 3.6 0" />
    </svg>
  )
}
