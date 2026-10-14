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

## 2026-10-14: Numerical contract v1 frozen
- **Reference:** `docs/numerical-contract.md`.
- **Inputs & Activations:** Signed INT8 `[-128, +127]`.
- **Weights:** Packed ternary codes (`00`: 0, `01`: +1, `10`: -1, `11`: invalid code triggering hardware error).
- **Arithmetic:** Sign-extended INT9 negation so `-(-128) = +128`; INT32 accumulation and bias.
- **Output scaling:** `multiplier` (UINT16), `shift` (0-31), symmetric round-half-away-from-zero, optional ReLU, and clamp to INT8.
- **Raw mode:** Bypass scaling for INT32 verification.

