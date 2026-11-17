import type { SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement>;

function base(props: IconProps) {
  return {
    width: 18,
    height: 18,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.8,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    "aria-hidden": true,
    ...props,
  };
}

export const Icons = {
  shield: (props: IconProps) => (
    <svg {...base(props)}>
      <path d="M12 3 5 6v6c0 4.2 2.8 7.4 7 9 4.2-1.6 7-4.8 7-9V6l-7-3Z" />
    </svg>
  ),
  upload: (props: IconProps) => (
    <svg {...base(props)}>
      <path d="M12 16V5" />
      <path d="m8 8 4-4 4 4" />
      <path d="M5 19h14" />
    </svg>
  ),
  file: (props: IconProps) => (
    <svg {...base(props)}>
      <path d="M7 3h7l5 5v13H7V3Z" />
      <path d="M14 3v5h5" />
    </svg>
  ),
  search: (props: IconProps) => (
    <svg {...base(props)}>
      <circle cx="11" cy="11" r="6" />
      <path d="m16 16 4 4" />
    </svg>
  ),
  sun: (props: IconProps) => (
    <svg {...base(props)}>
      <circle cx="12" cy="12" r="3.5" />
      <path d="M12 3v2M12 19v2M3 12h2M19 12h2M5.5 5.5l1.4 1.4M17.1 17.1l1.4 1.4M18.5 5.5l-1.4 1.4M6.9 17.1l-1.4 1.4" />
    </svg>
  ),
  moon: (props: IconProps) => (
    <svg {...base(props)}>
      <path d="M16 3.5A8 8 0 1 0 20.5 14 6.5 6.5 0 0 1 16 3.5Z" />
    </svg>
  ),
};
