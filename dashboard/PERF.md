# Dashboard performance baseline

Populated after first production deploy. Method (per plan A8):

```bash
for i in 1 2 3 4 5; do
  curl -w '%{time_total}\n' -o /dev/null -s https://${URL}/
done
```

Record the median across the four routes (`/`, `/aggregates`, `/monkeys`, `/ai`) from Sydney.

| Route | Median TTFB (Sydney, cold) | Notes |
|---|---|---|
| `/` | — | pending first deploy |
| `/aggregates` | — | pending first deploy |
| `/monkeys` | — | pending first deploy |
| `/ai` | — | pending first deploy |
