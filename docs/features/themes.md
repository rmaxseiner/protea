# Themes Feature

## Overview

Add user-selectable color schemes to the Protea web interface.

## Requirements

- Allow users to select from predefined color themes
- Persist theme preference per user (stored in database)
- Apply theme via CSS custom properties for easy switching
- Include light and dark mode variants

## Potential Themes

- Default (current blue/gray)
- Dark mode
- High contrast
- Nature/green
- Warm/amber

## Implementation Notes

- Store theme preference in users table or separate user_preferences table
- Use CSS variables for colors (already partially in place)
- Theme selector in Settings page
- Apply theme class to `<body>` or `:root` element
