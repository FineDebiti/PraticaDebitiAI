---
name: Institutional Heritage
colors:
  surface: '#f9f9f7'
  surface-dim: '#dadad8'
  surface-bright: '#f9f9f7'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f4f4f2'
  surface-container: '#eeeeec'
  surface-container-high: '#e8e8e6'
  surface-container-highest: '#e2e3e1'
  on-surface: '#1a1c1b'
  on-surface-variant: '#444841'
  inverse-surface: '#2f3130'
  inverse-on-surface: '#f1f1ef'
  outline: '#757871'
  outline-variant: '#c5c7bf'
  surface-tint: '#576151'
  primary: '#2d3628'
  on-primary: '#ffffff'
  primary-container: '#434d3e'
  on-primary-container: '#b2bdaa'
  inverse-primary: '#bfcab6'
  secondary: '#6c5c42'
  on-secondary: '#ffffff'
  secondary-container: '#f3ddbb'
  on-secondary-container: '#716045'
  tertiary: '#6b5d38'
  on-tertiary: '#ffffff'
  tertiary-container: '#bbaa7f'
  on-tertiary-container: '#4a3e1c'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#dbe6d2'
  primary-fixed-dim: '#bfcab6'
  on-primary-fixed: '#151e12'
  on-primary-fixed-variant: '#404a3b'
  secondary-fixed: '#f6dfbe'
  secondary-fixed-dim: '#d9c4a3'
  on-secondary-fixed: '#251a05'
  on-secondary-fixed-variant: '#53452c'
  tertiary-fixed: '#f4e1b2'
  tertiary-fixed-dim: '#d7c598'
  on-tertiary-fixed: '#241a00'
  on-tertiary-fixed-variant: '#524623'
  background: '#f9f9f7'
  on-background: '#1a1c1b'
  surface-variant: '#e2e3e1'
typography:
  headline-xl:
    fontFamily: Hanken Grotesk
    fontSize: 32px
    fontWeight: '700'
    lineHeight: 40px
  headline-lg:
    fontFamily: Hanken Grotesk
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
  headline-md:
    fontFamily: Hanken Grotesk
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
  body-lg:
    fontFamily: Hanken Grotesk
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-md:
    fontFamily: Hanken Grotesk
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  label-md:
    fontFamily: Hanken Grotesk
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0.02em
  button:
    fontFamily: Hanken Grotesk
    fontSize: 14px
    fontWeight: '600'
    lineHeight: 20px
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  sidebar-width: 260px
  container-max-width: 1280px
  gutter: 1.5rem
  stack-sm: 0.5rem
  stack-md: 1rem
  stack-lg: 2rem
---

## Brand & Style

This design system is rooted in the "Corporate / Modern" aesthetic, tailored specifically for the legal and financial sectors. It prioritizes stability, authority, and meticulous organization. The visual language conveys a sense of established trust through a palette that balances deep, earth-toned professionals (Olive) with warm, sophisticated accents (Gold/Tan).

The layout is structured and disciplined, utilizing clear containment and high-quality typography to ensure complex data remains legible and actionable. It avoids trend-driven flourishes in favor of a timeless, institutional feel that suggests long-term reliability and expertise in debt analysis.

## Colors

The color palette is derived from traditional legal and financial environments. 

- **Primary (Deep Olive):** Used for navigation sidebars and headers. It provides a strong, grounded foundation that commands authority.
- **Secondary (Gold/Tan):** Reserved for primary actions, selected states, and highlights. It introduces warmth and draws the eye to critical paths.
- **Neutral (Parchment & Stone):** The main content area utilizes off-white and very light grays to reduce eye strain during prolonged reading while maintaining a cleaner feel than pure white.
- **Semantic Colors:** Success, Error, and Warning states should be slightly desaturated to align with the professional tone of the palette.

## Typography

We use **Hanken Grotesk** across the system. It is a clean, sharp, and contemporary sans-serif that balances modern efficiency with professional precision. 

- **Headlines:** Use Bold or SemiBold weights in Primary Olive to establish clear information hierarchy.
- **Body Text:** Standardized at 14px and 16px for optimal legibility in data-heavy tables and documents.
- **Labels:** Uppercase or medium weights are used for form labels and metadata to differentiate them from user input.
- **Numerical Data:** Given the financial nature of the system, ensure tabular figures (monospaced numbers) are enabled where possible to ensure columns of figures align correctly.

## Layout & Spacing

The design system employs a **Fixed Sidebar + Fluid Content** layout model. 

- **Sidebar:** A persistent 260px vertical navigation bar on the left, using the Primary Olive color.
- **Main Content:** Follows a 12-column grid within a maximum width of 1280px. For wider screens, the content remains centered with margins.
- **Grid Strategy:** 24px (1.5rem) gutters and margins are standard.
- **Density:** The system uses a "Medium" density. Information is clustered logically within cards, but ample whitespace is maintained between sections to prevent cognitive overload during debt analysis tasks.
- **Mobile Adaptivity:** On mobile, the sidebar collapses into a bottom navigation bar or a hamburger menu, and the 12-column grid collapses to a single-column stack with 16px margins.

## Elevation & Depth

To maintain an institutional feel, the system uses **Low-Contrast Outlines** and **Tonal Layers** rather than heavy shadows.

- **Surface Tiers:** The background uses a light neutral (#F4F4F2), while primary content containers (cards) use pure white (#FFFFFF).
- **Outlines:** Containers and input fields use a subtle 1px border (#E2E2DE) to define boundaries.
- **Shadows:** When necessary (e.g., modals or dropdowns), use "Ambient Shadows"—extremely soft, diffused, and low-opacity (4-8%) with a hint of the primary green in the shadow color to maintain palette harmony.
- **Active States:** Depth is communicated through color shifts (e.g., a Gold background for an active tab) rather than physical extrusion.

## Shapes

The shape language is "Soft," utilizing small radii to take the edge off the interface without appearing overly casual or "bubbly."

- **Standard Elements:** Buttons, input fields, and small tags use a 0.25rem (4px) corner radius.
- **Large Containers:** Content cards and main panels use a 0.5rem (8px) radius.
- **Selections:** Navigation highlights in the sidebar may use a 0px radius on the outer edge (flush with the screen) while maintaining internal rounding to suggest a "tab" metaphor.

## Components

- **Buttons:** Primary buttons use the Gold (#A69375) background with white text. Secondary buttons use a transparent background with an Olive border. 
- **Input Fields:** Use a white background with a 1px neutral border. Placeholder text should be subtle gray. On focus, the border shifts to Gold.
- **Navigation Items:** Active states in the sidebar are indicated by a Gold highlight background and bolded text.
- **Data Tables:** Headers should have a dark background (Primary Olive) with white text for high contrast. Rows should alternate with a very subtle tint to assist in horizontal scanning.
- **Status Chips:** Small, pill-shaped indicators for case status (e.g., "Pending," "Resolved"). Use desaturated versions of semantic colors.
- **Cards:** Used to group related form fields or data summaries. Cards must have a clear 1px border and a white background to stand out from the neutral page background.