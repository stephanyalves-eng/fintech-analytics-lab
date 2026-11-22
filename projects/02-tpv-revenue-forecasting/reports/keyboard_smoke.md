# Keyboard smoke test — p2 (automated, partial)

> Automated Tab/arrow-key probe in headless Edge/Chrome against the running app (synthetic data). It is **not** an accessibility sign-off: a human keyboard pass and a screen-reader pass remain [TO VERIFY].

- Visible interactive candidates on the first tab: 67 (56 expected via Tab, 11 in arrow-key groups: tabs and radios).
- Tab presses: 174; distinct focus stops: 58; candidates never focused by Tab: 9 — input[]  tabindex=-1; input[]  tabindex=-1; button[] Open tabindex=-1; button[] Open tabindex=-1; button[] Open tabindex=-1; button[] Open tabindex=-1; button[] Open tabindex=-1; button[] Open tabindex=-1.
- Keyboard trap (same element keeps focus for 25+ consecutive Tab presses): none. Longest run: 9 extra presses on `canvas` (Streamlit data grids are canvases that use Tab to move across cells and then release focus; runs ≈ column count are expected).
- ArrowRight moves focus between tabs: True.
- Stops with zero size: 0.
- Stops with NO style change versus the pre-interaction state on the element or 5 ancestors (heuristic for a missing focus indicator; false negatives possible): 3 — main[] P2 · TPV, Revenue & Margin Forecasting S; canvas[] ; canvas[] .

First stops: a[] Skip to main content; span[spinbutton] year, Period (local dates) start date; span[spinbutton] month, Period (local dates) start date; span[spinbutton] day, Period (local dates) start date; span[spinbutton] year, Period (local dates) end date; span[spinbutton] month, Period (local dates) end date; span[spinbutton] day, Period (local dates) end date; button[] Choose date range; input[combobox] Country; input[combobox] Payment method; input[combobox] Merchant size tier; input[combobox] Merchant (overrides the method filter).
