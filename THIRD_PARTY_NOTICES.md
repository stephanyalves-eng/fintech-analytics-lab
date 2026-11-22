# Third-party notices

The repository code is MIT-licensed (see `LICENSE`). It uses or vendors the third-party components below.
This file records provenance; it does not replace the upstream license texts.

## Vendored file

| Component | Version | License | File | SHA-256 |
|---|---|---|---|---|
| axe-core (Deque Systems, Inc.) | 4.10.2 | MPL-2.0 | `shared/vendor/axe.min.js` | `b511cd9dec01c76f4b2ad1723b66b6db37d4c2eb4ed199076e1829d9ee7b75e3` |

- Source: <https://github.com/dequelabs/axe-core> (license text: <https://www.mozilla.org/MPL/2.0/>).
- The file is **unmodified** and keeps its upstream copyright/license header. It is only injected into the locally
  running dashboards by `projects/02-tpv-revenue-forecasting/app/a11y_audit.py` and
  `projects/03-experimentation-lab/app/a11y_audit.py` for the automated accessibility check; nothing is sent
  outside the machine. Both scripts refuse to run if the SHA-256 above does not match.
- `.gitattributes` marks the file `-text` so checkout line-ending conversion cannot change its bytes.
- MPL-2.0 applies to this file only (file-level copyleft); it does not extend to the rest of the repository.

## Python dependencies (not redistributed)

Installed from PyPI via `requirements-lock.txt`; licenses below are read from the installed package metadata
(versions as locked). They are listed for transparency, not legal advice.

| Package | Version | License (package metadata) |
|---|---|---|
| duckdb | 2.0.1 | MIT |
| pandas | 3.1.1 | BSD-3-Clause |
| numpy | 2.5.5 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 |
| pyarrow | 26.0.1 | Apache-2.0 |
| pyyaml | 6.0.4 | MIT |
| scipy | 1.18.1 | BSD |
| statsmodels | 0.15.0 | BSD-3-Clause |
| plotly | 7.1.0 | MIT |
| streamlit | 1.67.0 | Apache-2.0 |
| websockets | 17.4 | BSD-3-Clause |
| pytest (dev) | 9.2.0 | MIT |
| ruff (dev) | 0.17.6 | MIT |

The remaining transitive packages in `requirements-lock.txt` were not individually reviewed `[TO VERIFY]`.

## Data

All datasets are generated locally by the code in this repository and are synthetic; no third-party data is
included or redistributed. The public Olist dataset mentioned in the blueprint is **not** used.
