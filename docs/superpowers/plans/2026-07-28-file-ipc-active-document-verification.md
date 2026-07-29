# File IPC Active-Document Verification Plan

**Status:** Completed on `4656e9f148bcd90c43c9eba672fdd5977f8cc307`

**Base SHA:** `3beb1f4cb0ebf17b16822598f8c6ab617aa955e7`

## Steps

1. Reproduce and isolate the release live-gate failure.
2. Add failing offline tests for full-path active-document verification and safe
   read-only retry.
3. Implement one verified open retry and one attribute-read timeout retry.
4. Run focused offline tests and the previously failing live component test.
5. Completed: the final verifier passed 353 offline tests; the private gate
   passed; the five-test live gate passed, including same-name/different-path.
