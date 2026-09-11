# Receiver-Identity Diagnostic — Iteration 63

Date: 2026-09-11 (Asia/Saigon)
Branch: `codex/audit-text-style-compat-20260910`
Reviewed code head: `65fc23ba610091e236f19ee93f8cee69f96d4ce9`
Evidence/docs head before this record: `0a6b1fa540b3719edd59cc699f9176162a935ca7`

## Authority and boundary

SOL's iteration-62 diagnosis was:

```text
VERDICT=MATERIAL_FINDING
MATERIAL_FINDING=FIRST_CAUSAL_BOUNDARY=WINDOW_RECEIVER_OR_COMMAND_DELIVERY_SEMANTICS_NOT_PROVEN
HUMAN_GATE=NO
```

The authorized single bounded diagnostic was:

```text
fresh disposable QNEW
same-HWND document-ready
enumerate owned AutoCAD child-window hierarchy
capture active/focus/capture identities for the actual GUI thread
compare with the MDIClient selected by the existing trigger
close/cleanup
```

It was observation-only. It did not send `WM_CHAR`, raw-LISP, or any command;
use a focus workaround; load NETLOAD or dispatcher; issue FileIPC or Task-6;
access source/candidate/DXF; retry; or mutate production CAD state.

## Receiver and GUI-thread observation

The disposable session reached document-ready with:

```text
owned_window: hwnd=7406996 class=AfxMDIFrame140u pid=29440 visible=true
owned_gui_thread_id=23156
foreground_window: hwnd=7406996 class=AfxMDIFrame140u pid=29440 visible=true
foreground_gui_thread_id=23156
```

The complete child-window inventory captured under the owned main window was:

```text
hwnd=8521664  class=MDIClient                                      pid=29440 visible=true
hwnd=5770910  class=Afx:00007FF77AB10000:b:0000000000010003:0000000000000006:00000000040602AF pid=29440 visible=true title=Drawing1.dwg
hwnd=17172886 class=msctls_statusbar32                            pid=29440 visible=false
hwnd=7015674  class=AfxWnd140u                                    pid=29440 visible=false
hwnd=5180418  class=Afx:00007FF77AB10000:28:0000000000000000:0000000000000002:0000000021160559 pid=29440 visible=true
hwnd=3867880  class=ACADDM_CHILD_DXGI_FLIP_MODE_VIEW_CLASS         pid=29440 visible=true
hwnd=1904298  class=Afx:00007FF77AB10000:3:0000000000010003:0000000000000006:000000003D900E5D pid=29440 visible=true title=Start
hwnd=4394534  class=Chrome_WidgetWin_0                          pid=29440 visible=false
hwnd=4065632  class=Chrome_WidgetWin_1                          pid=31216 visible=false title=about:blank
hwnd=5965954  class=Chrome_RenderWidgetHostHWND                  pid=31216 visible=false title=Chrome Legacy Window
hwnd=5115060  class=Intermediate D3D Window                      pid=12428 visible=false
hwnd=9440858  class=AdImpApplicationFrame                       pid=29440 visible=true title=AdImpApplicationFrame
hwnd=5769106  class=HwndWrapper[DefaultDomain;;16db0369-7872-4b90-9cb6-1d66dba117eb] pid=29440 visible=true title=InfoCenterHwndSource
hwnd=5244534  class=MDIClient                                      pid=29440 visible=false
hwnd=14157554 class=HwndWrapper[DefaultDomain;;39c4cc70-58e9-496f-a9b9-c3c81ecaa6ed] pid=29440 visible=false title=QATHwndSource
hwnd=9897658  class=msctls_statusbar32                            pid=29440 visible=false
hwnd=7278284  class=AfxControlBar140u                             pid=29440 visible=true
hwnd=1180472  class=AfxControlBar140u                             pid=29440 visible=true
hwnd=5180454  class=#32770                                         pid=29440 visible=false
hwnd=12978492 class=AfxControlBar140u                             pid=29440 visible=true
hwnd=4721362  class=#32770                                         pid=29440 visible=false
hwnd=7604128  class=AfxControlBar140u                             pid=29440 visible=true
hwnd=8193266  class=Chrome_WidgetWin_0                          pid=29440 visible=false
hwnd=8260196  class=Chrome_WidgetWin_1                          pid=31216 visible=false title=installed-components.autodesk/autocad.swclient.html?componenturl=https://prd.autocad.com&appagent=Autodesk/ACAD/26.0/en-US/A101&appbuildID=X.118.0.0
hwnd=6423962  class=Chrome_RenderWidgetHostHWND                  pid=31216 visible=false title=Chrome Legacy Window
hwnd=4590824  class=Intermediate D3D Window                      pid=12428 visible=false
```

The existing trigger's exact selection rule produced:

```text
mdi_candidates:
  visible  hwnd=8521664 class=MDIClient pid=29440
  hidden   hwnd=5244534 class=MDIClient pid=29440
owned_mdi_candidates=2
visible_owned_mdi_candidates=1
existing_trigger_selected_mdi=8521664
selection_is_unique=true
```

The owner GUI thread reported:

```text
active:  hwnd=7406996 class=AfxMDIFrame140u pid=29440 visible=true
focus:   hwnd=5180418 class=Afx:00007FF77AB10000:28:0000000000000000:0000000000000002:0000000021160559 pid=29440 visible=true
capture: hwnd=0
```

The selected `MDIClient` is therefore a unique visible owned receiver, while
the actual focused child is HWND `5180418`. This narrows the receiver/delivery
boundary but does not establish that posting to the selected `MDIClient` is the
cause of the missing marker.

## Cleanup and safety

- The initial close call reported
  `MCPTimeoutError: START_TAB_BOOTSTRAP_CLOSE_NOT_CONFIRMED`.
- The bounded cleanup fallback closed the exact disposable PID `29440` without
  saving; a follow-up process check found PID `29440` absent.
- The proof root
  `C:/temp/cad-agent-task6-live-20260911/receiver-identity-proof-iteration63`
  had no remaining entries.
- No source, candidate, accepted drawing, DXF, FileIPC request, or production
  CAD state changed. No production code changed.
- Fresh SOL diagnosis is required before any trigger retry or implementation
  change.
