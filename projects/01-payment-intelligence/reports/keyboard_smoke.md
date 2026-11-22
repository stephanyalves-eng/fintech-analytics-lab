# Keyboard smoke test — p1 (automated, partial)

> Automated Tab/arrow-key probe in headless Edge/Chrome against the running app (synthetic data). It is **not** an accessibility sign-off: a human keyboard pass and a screen-reader pass remain [TO VERIFY].

- Visible interactive candidates on the first tab: 55 (49 expected via Tab, 6 in arrow-key groups: tabs and radios).
- Tab presses: 150; distinct focus stops: 39; candidates never focused by Tab: 13 — input[]  tabindex=-1; input[]  tabindex=-1; button[] Open tabindex=-1; button[] Open tabindex=-1; button[] Open tabindex=-1; button[] Show/hide columns tabindex=null; button[] Download as CSV tabindex=null; button[] Search tabindex=null.
- Keyboard trap (same element keeps focus for 25+ consecutive Tab presses): none. Longest run: 0 extra presses on `-` (Streamlit data grids are canvases that use Tab to move across cells and then release focus; runs ≈ column count are expected).
- ArrowRight moves focus between tabs: True.
- Stops with zero size: 0.
- Stops with NO style change versus the pre-interaction state on the element or 5 ancestors (heuristic for a missing focus indicator; false negatives possible): 1 — main[] Payment Intelligence SYNTHETIC DATA · de.

First stops: a[] Skip to main content; button[] Help for Payment creation date (merchant; span[spinbutton] year, Payment creation date (merchant lo; span[spinbutton] month, Payment creation date (merchant l; span[spinbutton] day, Payment creation date (merchant loc; span[spinbutton] year, Payment creation date (merchant lo; span[spinbutton] month, Payment creation date (merchant l; span[spinbutton] day, Payment creation date (merchant loc; button[] Choose date range; input[combobox] Country; input[combobox] Payment method; input[combobox] Acquirer.
