# Model IDs and prices

Source: Nebius Token Factory model catalog, Base public endpoints, read 2026-09-23.
Nebius marks prices as approximate; the dashboard usage is the billing truth.

| role | model ID | USD / 1M in | USD / 1M out | speed shown |
|---|---|---|---|---|
| small, small_think | nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B | 0.06 | 0.24 | 60 tok/s |
| large | openai/gpt-oss-120b | 0.15 | 0.60 | 40 tok/s |
| baseline_open | deepseek-ai/DeepSeek-V4-Pro | TBD | TBD | TBD |

USD_TO_EUR = 1 / 1.1463 = 0.872372
ECB euro reference rate for 2026-09-22 (latest published at time of writing), 1 EUR = 1.1463 USD.
Source: https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml

Notes
- Nemotron-3-Nano-30B-A3B: LoRA fine-tuning not available on Nebius (model card). No "finetuned" row on this base.
- Budget: Nebius trial credit is $1.00.
