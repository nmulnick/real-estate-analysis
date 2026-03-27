# Print / PDF Manual QA Checklist

Run this checklist after any changes to print CSS or layout.
Open the dashboard in Chrome, click "Print / PDF" button, and verify each item in the print preview.

## Layout
- [ ] Sidebar is completely hidden
- [ ] Share Link and Print / PDF buttons are hidden
- [ ] Recalculate Now button is hidden
- [ ] Main content is full-width (no sidebar gap)
- [ ] No horizontal overflow or scrollbars

## Header
- [ ] Header gradient renders with colors (not white)
- [ ] Title and subtitle are visible
- [ ] "Generated [date]" timestamp is visible
- [ ] Shareable URL is visible below the timestamp
- [ ] Print/Share buttons are NOT visible

## KPI Cards
- [ ] All 5 KPI cards visible on one row
- [ ] Card backgrounds/borders render
- [ ] Values and detail text are readable

## Charts
- [ ] All 4 charts render as images (not blank/white)
- [ ] Charts are single-column layout (full width each)
- [ ] Chart labels and axes are readable
- [ ] No chart is cut off at a page break

## Tables
- [ ] Scenario A table is complete and readable
- [ ] Scenario B table is complete with all exit scenario columns
- [ ] NPV comparison table is present
- [ ] IRR table is present with verdict badges
- [ ] Annual Cash Flow table is present (all years)
- [ ] Colored cells (cell-a blue, cell-b green) print with color

## Sensitivity Analysis
- [ ] All 4 sensitivity tables are visible
- [ ] Colored winner cells (blue/green) print correctly
- [ ] Font size is readable (not too small)
- [ ] Tables are not clipped or overflowing

## Assumptions Summary
- [ ] Key Assumptions table is present at bottom
- [ ] All assumption values are shown

## Tooltips
- [ ] Tooltip question mark icons (?) are hidden in print

## Cross-Browser
- [ ] Repeat above checks in Safari
- [ ] If Safari shows blank canvases, file a bug for canvas-to-image fallback

## Page Breaks
- [ ] No card or chart is split across two pages
- [ ] Content flows naturally across pages
- [ ] No large blank areas between sections
