# Readable reports (0.9)

Timoshenko calculation results remain available as Python objects and JSON dictionaries. The report module adds a human-readable, self-contained HTML view for the same evidence:

```python
import timoshenko as tm

result = tm.run_project("project/manifest.json")
html = tm.report.to_html(result)
path = tm.report.save_html(result, "reports/bridge-analysis.html")
```

The functions accept `MonitoringResult`, `SessionReport`, or `ProjectRunResult`. HTML contains an embedded accessible SVG comparing identified frequencies with available model references, a table of frequencies/differences/damping, method and evidence status, limitations, and the SHA-256 input/manifest hashes when present. The report is rendered locally and requires no JavaScript, web service, or chart package. `save_html` writes UTF-8 and returns the resolved destination path.

All dynamic text is HTML-escaped. Reports show the result provided by the caller and do not add thresholds, classify risk, infer damage, or convert an evidence comparison into a safety judgement. SVG chart scaling uses the largest reference or observed frequency in that result; it is a compact comparison view, not a spectrum plot.
