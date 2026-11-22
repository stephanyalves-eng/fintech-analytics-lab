# Keyboard smoke test — p3 (automated, partial)

> Automated Tab/arrow-key probe in headless Edge/Chrome against the running app (synthetic data). It is **not** an accessibility sign-off: a human keyboard pass and a screen-reader pass remain [TO VERIFY].

- Visible interactive candidates on the first tab: 33 (21 expected via Tab, 12 in arrow-key groups: tabs and radios).
- Tab presses: 106; distinct focus stops: 10; candidates never focused by Tab: 14 — a[] Link to heading tabindex=null; a[]  tabindex=null; a[]  tabindex=null; a[] Link to heading tabindex=null; a[] Link to heading tabindex=null; a[] Link to heading tabindex=null; a[] Link to heading tabindex=null; a[] Link to heading tabindex=null.
- Keyboard trap (same element keeps focus for 25+ consecutive Tab presses): none. Longest run: 0 extra presses on `-` (Streamlit data grids are canvases that use Tab to move across cells and then release focus; runs ≈ column count are expected).
- ArrowRight moves focus between tabs: True.
- Stops with zero size: 0.
- Stops with NO style change versus the pre-interaction state on the element or 5 ancestors (heuristic for a missing focus indicator; false negatives possible): 1 — main[] P3 · A/B Testing Lab SYNTHETIC DATA Expe.

First stops: a[] Skip to main content; input[] 1; button[] Deploy; button[] Main menu; main[] P3 · A/B Testing Lab SYNTHETIC DATA Expe; a[] Link to heading; div[tab] Overview & protocol; a[] Link to heading; button[] Help for Protocol; summary[] keyboard_arrow_right Preregistered proto.
