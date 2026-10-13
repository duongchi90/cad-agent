# TRANSFER_ORACLE: Polyline Bulge Transfer Test & Verification Oracle

## Exact Mathematical Implementation & Deterministic Unit Tests

```python
import math

def points_to_bulge(p1: tuple[float, float], p2: tuple[float, float], p3: tuple[float, float]) -> float:
    """
    Calculate the exact DXF LWPOLYLINE bulge parameter for an arc segment starting at p1,
    passing through p2, and ending at p3.
    
    Definition:
      bulge = tan(included_angle / 4)
      Positive for Counter-Clockwise (CCW) arc.
      Negative for Clockwise (CW) arc.
      0.0 for straight line segment (collinear).
    """
    x1, y1 = p1
    x2, y2 = p2
    x3, y3 = p3
    
    # 2D cross product for orientation and collinearity test
    cross = (x2 - x1) * (y3 - y1) - (y2 - y1) * (x3 - x1)
    if abs(cross) < 1e-9:
        return 0.0  # Collinear points -> straight line segment
        
    dx = x3 - x1
    dy = y3 - y1
    chord_len_sq = dx * dx + dy * dy
    if chord_len_sq < 1e-12:
        return 0.0  # Degenerate zero-length chord
        
    # Circle center calculation via perpendicular bisector intersection
    d = 2.0 * cross
    xc = ((x2*x2 - x1*x1 + y2*y2 - y1*y1)*(y3 - y1) - (x3*x3 - x1*x1 + y3*y3 - y1*y1)*(y2 - y1)) / d
    yc = ((x3*x3 - x1*x1 + y3*y3 - y1*y1)*(x2 - x1) - (x2*x2 - x1*x1 + y2*y2 - y1*y1)*(x3 - x1)) / d
    
    # Angular traversal from circle center (xc, yc):
    a1 = math.atan2(y1 - yc, x1 - xc)
    a2 = math.atan2(y2 - yc, x2 - xc)
    a3 = math.atan2(y3 - yc, x3 - xc)
    
    # Normalize traversal angles relative to a1
    da2 = (a2 - a1) % (2.0 * math.pi)
    da3 = (a3 - a1) % (2.0 * math.pi)
    
    # If da2 < da3, the traversal visits p2 while traveling CCW from p1 to p3
    if da2 < da3:
        # Counter-Clockwise arc
        included_angle = da3
        bulge = math.tan(included_angle / 4.0)
    else:
        # Clockwise arc
        included_angle = 2.0 * math.pi - da3
        bulge = -math.tan(included_angle / 4.0)
        
    # Stability guard: near-zero bulge snaps to straight line
    if abs(bulge) < 1e-7:
        return 0.0
        
    return bulge


def test_bulge_oracle():
    # Test 1: Semicircle CW from (0,0) through (5,5) to (10,0) (Center is (5,0), angle: pi -> pi/2 -> 0)
    b1 = points_to_bulge((0.0, 0.0), (5.0, 5.0), (10.0, 0.0))
    assert math.isclose(b1, -1.0, rel_tol=1e-5), f"Expected -1.0, got {b1}"
    
    # Test 2: Semicircle CCW from (10,0) through (5,5) to (0,0) (Angle: 0 -> pi/2 -> pi)
    b2 = points_to_bulge((10.0, 0.0), (5.0, 5.0), (0.0, 0.0))
    assert math.isclose(b2, 1.0, rel_tol=1e-5), f"Expected 1.0, got {b2}"
    
    # Test 3: Straight line segment (collinear) -> bulge must be 0.0
    b3 = points_to_bulge((0.0, 0.0), (5.0, 0.0), (10.0, 0.0))
    assert b3 == 0.0, f"Expected 0.0, got {b3}"
    
    # Test 4: Quarter circle CCW (90 deg arc) from (10,0) through (7.071, 7.071) to (0,10)
    # Expected bulge: tan(90 deg / 4) = tan(22.5 deg) = sqrt(2) - 1 ~= 0.41421356
    p2 = (10.0 * math.cos(math.pi/4), 10.0 * math.sin(math.pi/4))
    b4 = points_to_bulge((10.0, 0.0), p2, (0.0, 10.0))
    expected_b4 = math.tan(math.pi / 8)
    assert math.isclose(b4, expected_b4, rel_tol=1e-5), f"Expected {expected_b4}, got {b4}"
    
    print("ALL BULGE ORACLE TESTS PASSED (100% PASS RATE)")

if __name__ == "__main__":
    test_bulge_oracle()
```
