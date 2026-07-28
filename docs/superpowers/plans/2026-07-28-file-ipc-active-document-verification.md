# File IPC Active-Document Verification Plan

**Status:** In progress

**Base SHA:** `3beb1f4cb0ebf17b16822598f8c6ab617aa955e7`

## Steps

1. Reproduce and isolate the release live-gate failure.
2. Add failing offline tests for active-document verification and safe
   read-only retry.
3. Implement one verified open retry and one attribute-read timeout retry.
4. Run focused offline tests and the previously failing live component test.
5. Commit, run the complete verifier/private/live gates, and record evidence.
