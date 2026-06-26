---
version: "1.0"
theme: "Deep Space Dark Mode"
colors:
  background: "#08090C"
  surface: "rgba(17, 20, 28, 0.7)"
  border: "rgba(255, 255, 255, 0.08)"
  text_primary: "#FFFFFF"
  text_secondary: "#8F9CAE"
  accent_primary: "#8B5CF6"      # Vibrant violet/purple
  accent_secondary: "#06B6D4"    # Neon cyan
  highlight: "#FBBF24"           # Neon yellow (for selected pocket residues)
  success: "#10B981"
  error: "#EF4444"
typography:
  font_heading: "Montserrat, sans-serif"
  font_body: "Inter, sans-serif"
  size_base: "16px"
---

# Design System Manifest: AlignX Web Application

This document defines the visual rules and styling system for the production-grade web version of AlignX. It maintains visual consistency across both frontend components and AI-generated modules.

---

## 🎨 Overview & Aesthetic Vibe
The visual aesthetic follows a **modern, scientific, and high-tech dark mode**. 
- **Glassmorphism**: Semi-transparent dark card surfaces with thin white borders and strong backdrop blurring (`backdrop-filter: blur(12px)`).
- **Vibrant Accent Gradients**: Gradients transitioning from deep violet (`#8B5CF6`) to neon cyan (`#06B6D4`) for headers and primary interactions.
- **High Readability**: Crisp sans-serif typography, clean visual hierarchy, and high contrast for numerical structure metrics.

---

## 🎨 Core Color Palette

- **Background**: `#08090C` (Absolute deep space dark)
- **Surfaces**: `rgba(17, 20, 28, 0.7)` (Translucent charcoal glass)
- **Borders**: `rgba(255, 255, 255, 0.08)` (Thin glowing divider lines)
- **Primary Text**: `#FFFFFF` (Pure white)
- **Secondary Text**: `#8F9CAE` (Muted gray-blue)
- **Interactive Highlight**: `#FBBF24` (Neon yellow sticks, spheres, and labels for active pocket selections)

---

## 📐 Layout & Spacing
- **Base Grid Unit**: `8px`
- **Page Container**: Max-width `1440px`, centered, padding `24px`
- **Sidebar**: Persistent left-side setup panel, width `280px`
- **Grid Layout**: Responsive 2-column or 3-column CSS Grid layout with a default gap of `24px`

---

## 📦 Component Styling

### 1. Cards
- **Background**: `rgba(17, 20, 28, 0.7)`
- **Border**: `1px solid rgba(255, 255, 255, 0.08)`
- **Border Radius**: `12px`
- **Shadow**: `0 8px 32px 0 rgba(0, 0, 0, 0.37)`
- **Blur**: `backdrop-filter: blur(12px)`

### 2. Buttons
- **Primary Button**: Solid gradient from `#8B5CF6` to `#06B6D4`, text `#FFFFFF`, border-radius `8px`, transition `all 0.2s ease`.
- **Secondary Button**: Transparent background, border `1px solid rgba(255, 255, 255, 0.15)`, text `#FFFFFF`, border-radius `8px`.
- **Active Pills**: Muted secondary color with standard `8px` radius.

### 3. Data Tables
- **Header**: Background `rgba(255, 255, 255, 0.03)`, text `#8F9CAE`, weight `600`.
- **Rows**: Alternating subtle backgrounds, hover background `rgba(255, 255, 255, 0.02)`.
- **Selected Row**: Border `1px solid #FBBF24`, background `rgba(251, 191, 36, 0.08)`.

### 4. 3D Viewport Panels
- **Layout**: Crisp dark canvases with rounded `12px` corners.
- **Labels**: Muted dark background `rgba(17, 20, 28, 0.88)` with white text and a thin border matching the model's chain color.
