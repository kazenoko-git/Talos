# Talos 2 decision log

## Established direction

- General-purpose small embedded inference accelerator.
- Programmable ternary weights and signed INT8 activations; INT32 accumulation.
- Current physical limit: 2×2 tiles.
- External model/working memory; one shared arithmetic engine initially.
- Custom carrier board is permitted by the organizer.

## Candidates requiring measurement

- 64-byte input buffer and four partial sums.
- Output scaling implementation and its numerical profile.
- Shared SPI/QSPI memory bus and actual flash/RAM devices.
- Final clock target, safe host SPI rate, and pin assignment.

The implementation plan distinguishes required capabilities from these candidates. Record each change with its reason, reference/test impact, and measured area/timing/accuracy evidence.
