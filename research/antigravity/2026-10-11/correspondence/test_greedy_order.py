import sys
sys.path.insert(0, r"C:\Users\duong\ZCodeProject\cad-agent")

# Test greedy order dependency
def test_greedy_vs_global():
    print("=== TESTING GREEDY VS GLOBAL ASSIGNMENT PATHOLOGY ===")
    
    # Base lines: B1 at y=50, B2 at y=52
    # Target lines:
    # T1 at y=50.8: dist(B1)=0.8, dist(B2)=1.2
    # T2 at y=49.5: dist(B1)=0.5, dist(B2)=2.5
    # max_residual = 1.5
    
    bases = {"B1": 50.0, "B2": 52.0}
    max_res = 1.5
    
    def run_greedy(targets):
        used_bases = set()
        matches = []
        for tid, ty in targets:
            costs = [(abs(ty - by), bid) for bid, by in bases.items()]
            costs.sort(key=lambda x: x[0])
            best_res, best_bid = costs[0]
            if best_res > max_res:
                return "NO_SUPPORTED_DELTA"
            if len(costs) > 1 and costs[0][0] == costs[1][0]:
                return "AMBIGUOUS (TIE)"
            if best_bid in used_bases:
                return "AMBIGUOUS (COLLISION)"
            used_bases.add(best_bid)
            matches.append((tid, best_bid, best_res))
        return matches

    order_1 = [("T1", 50.8), ("T2", 49.5)]
    res_1 = run_greedy(order_1)
    print("Order [T1, T2] result:", res_1)

    order_2 = [("T2", 49.5), ("T1", 50.8)]
    res_2 = run_greedy(order_2)
    print("Order [T2, T1] result:", res_2)

if __name__ == "__main__":
    test_greedy_vs_global()
