---
name: Clinical Resilience
colors:
  surface: '#f6fafe'
  surface-dim: '#d6dade'
  surface-bright: '#f6fafe'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f0f4f8'
  surface-container: '#eaeef2'
  surface-container-high: '#e4e9ed'
  surface-container-highest: '#dfe3e7'
  on-surface: '#171c1f'
  on-surface-variant: '#44474f'
  inverse-surface: '#2c3134'
  inverse-on-surface: '#edf1f5'
  outline: '#747780'
  outline-variant: '#c4c6d0'
  surface-tint: '#425e91'
  primary: '#002452'
  on-primary: '#ffffff'
  primary-container: '#1b3a6b'
  on-primary-container: '#89a5dd'
  inverse-primary: '#acc7ff'
  secondary: '#2e6b2e'
  on-secondary: '#ffffff'
  secondary-container: '#adf0a4'
  on-secondary-container: '#326f32'
  tertiary: '#520400'
  on-tertiary: '#ffffff'
  tertiary-container: '#7a0a00'
  on-tertiary-container: '#ff8069'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#d7e2ff'
  primary-fixed-dim: '#acc7ff'
  on-primary-fixed: '#001a40'
  on-primary-fixed-variant: '#294678'
  secondary-fixed: '#b0f3a6'
  secondary-fixed-dim: '#95d78d'
  on-secondary-fixed: '#002203'
  on-secondary-fixed-variant: '#135218'
  tertiary-fixed: '#ffdad4'
  tertiary-fixed-dim: '#ffb4a6'
  on-tertiary-fixed: '#3f0300'
  on-tertiary-fixed-variant: '#900e00'
  background: '#f6fafe'
  on-background: '#171c1f'
  surface-variant: '#dfe3e7'
typography:
  headline-lg:
    fontFamily: Public Sans
    fontSize: 24px
    fontWeight: '700'
    lineHeight: 32px
  headline-md:
    fontFamily: Public Sans
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
  body-lg:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '400'
    lineHeight: 26px
  body-md:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  label-xl:
    fontFamily: Inter
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
  label-bold:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '700'
    lineHeight: 20px
  button:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '600'
    lineHeight: 18px
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  container-padding: 16px
  stack-gap: 12px
  section-gap: 24px
  touch-target-min: 48px
  nav-height: 56px
---

## Brand & Style

This design system is built for the frontline health workers of the Philippines. The brand personality is **Trustworthy, Calm, and Clinical**, prioritizing clarity and speed of use in high-pressure medical environments. The aesthetic follows a **Corporate / Modern** style, borrowing from Material Design principles but optimized for the specific ergonomics of a mobile-first PWA.

The UI evokes a sense of institutional reliability. It uses a high-contrast palette to ensure legibility under various lighting conditions (e.g., outdoor community check-ups). Every element is oversized and tactile to accommodate rapid data entry and "fat-finger" interactions. The emotional goal is to reduce cognitive load and provide a stable, guided experience for the user.

## Colors

The color strategy uses deep, authoritative tones to establish trust. **Navy (#1B3A6B)** serves as the primary structural color, used for headers and primary actions to signify importance. **Forest Green (#2D6A2D)** and **Deep Red (#AC1B07)** are reserved strictly for clinical status signaling.

Special attention is given to the **Critical Triage State**, which utilizes the tertiary **Deep Red (#AC1B07)** for high visibility and immediate urgency. This replaces previous yellow warning states to streamline decision-making into high-priority vs. stable categories. The background uses a soft **Light Gray (#F0F4F8)** to reduce screen glare and distinguish the white card surfaces.

## Typography

This design system utilizes **Public Sans** for headings to provide a clean, institutional feel that is highly legible. **Inter** is used for body and labels to leverage its systematic, utilitarian nature.

To accommodate Barangay Health Workers who may be working in bright sunlight or have varied visual acuity, the minimum body size is set to **16px**. Key labels and identifiers use **20px+** to ensure critical data points are never missed. Clinical results and triage outcomes must always use the **Bold** weight to differentiate them from instructional text.

## Layout & Spacing

This design system uses a **Fluid Grid** model optimized for mobile viewports. The layout relies on a strict **16px horizontal margin** for all main content containers. 

Vertical spacing follows a 4px baseline rhythm, with a standard **12px gap** between related items in a list and **24px** between distinct sections. Elements are designed to stretch the full width of the mobile screen minus the 16px padding to maximize the touchable area. The bottom navigation is fixed at **56px tall**, ensuring it remains accessible to the thumb at all times.

## Elevation & Depth

This design system uses **Tonal Layers** combined with **Ambient Shadows** to create a clear hierarchy on the light gray background.

- **Level 0 (Background):** Light Gray (#F0F4F8).
- **Level 1 (Cards/Surfaces):** White (#FFFFFF) with a subtle shadow (0px 2px 4px rgba(27, 58, 107, 0.08)). These are the primary containers for patient data.
- **Level 2 (Overlays/Modals):** White (#FFFFFF) with a more pronounced shadow (0px 8px 16px rgba(27, 58, 107, 0.15)) to indicate temporary interaction.

Shadows are slightly tinted with the Primary Navy color to maintain a cohesive, "clinical" color temperature rather than using neutral blacks.

## Shapes

The shape language is **Rounded**, using a varied corner radius strategy to imply containment and hierarchy. Cards use a **16px radius** for a soft, friendly appearance that feels professional yet approachable. Buttons utilize a **12px radius**, providing a distinct shape that is easily recognizable as an interactive element. Input fields use a tighter **8px radius** to maintain a structured, organized feel for data entry forms.

## Components

### Buttons
- **Primary:** Navy (#1B3A6B) background, White text, 52px height, 12px radius.
- **Secondary:** White background, Navy 1px border, Navy text, 52px height.
- **Critical/Danger:** Deep Red (#AC1B07) background, White text, 52px height.

### Input Fields
- **Standard Field:** 48px minimum height, 1px Navy border, 8px radius, White background. 
- **Focus State:** 2px Navy border for clear accessibility.

### Triage Badges
- Full-width elements, **72px height**, 12px radius.
- **Stable (Green):** Forest Green background, White bold text.
- **Critical (Red):** Deep Red (#AC1B07) background, White bold text.

### Cards
- White background, 16px radius, subtle ambient shadow. 
- Padding: 16px internal padding for content.

### Navigation
- **Bottom Nav:** 56px height, Navy background or White with Navy icons.
- **Pasyente Button:** Center-aligned, larger than other icons, visually distinct to highlight the primary "Add/View Patient" workflow.

### Lists
- Patient records should be displayed as cards with high-contrast labels for "Name" and "Triage Status."