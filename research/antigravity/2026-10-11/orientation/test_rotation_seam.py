import math
import numpy as np

# Simulate estimate_similarity_alignment from geometry_alignment.py
def test_rotation_parameter():
    # 90 degree rotated target vs base
    # Target points in mm (calibrated): (100, 100), (300, 100), (100, 250)
    target_pts = np.array([[100.0, 100.0], [300.0, 100.0], [100.0, 250.0]])
    
    # 90-degree CCW rotation in WCS + translation (500, 400)
    theta = math.radians(90.0)
    R = np.array([[math.cos(theta), -math.sin(theta)], [math.sin(theta), math.cos(theta)]])
    t = np.array([500.0, 400.0])
    base_pts = (R @ target_pts.T).T + t
    
    # Fit with max_rotation_deg = 5.0 (current default)
    source_centroid = target_pts.mean(axis=0)
    target_centroid = base_pts.mean(axis=0)
    source_centered = target_pts - source_centroid
    target_centered = base_pts - target_centroid
    
    covariance = source_centered.T @ target_centered
    left, singular_values, right_transposed = np.linalg.svd(covariance)
    row_rotation = left @ right_transposed
    source_energy = float(np.sum(source_centered * source_centered))
    uniform_scale = float(np.sum(singular_values) / source_energy)
    linear = uniform_scale * row_rotation.T
    rot_deg = math.degrees(math.atan2(float(linear[1, 0]), float(linear[0, 0])))
    
    print(f"Computed uniform_scale: {uniform_scale:.6f}")
    print(f"Computed rotation_deg:  {rot_deg:.2f}°")
    print(f"Scale within 1e-6 of 1.0: {abs(uniform_scale - 1.0) <= 1e-6}")
    print(f"Default max_rotation_deg=5.0 passes: {abs(rot_deg) <= 5.0}")
    print(f"Permissive max_rotation_deg=360.0 passes: {abs(rot_deg) <= 360.0}")

if __name__ == "__main__":
    test_rotation_parameter()
