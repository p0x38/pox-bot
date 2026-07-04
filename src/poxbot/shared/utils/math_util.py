import numpy as np


def approach_target(
    target: float,
    max_iterations: int = 125,
    x: float = 1.75,
    current_range: tuple[float, float] = (-5.0, 5.0),
    step_variance: tuple[float, float] = (0.5, 2.0),
    seed: int | None = None,
) -> list[float]:
    rng = np.random.default_rng(seed)
    
    cmin, cmax = current_range
    current = target + rng.uniform(cmin, cmax)
    
    history: list[float] = [current]
    
    smin, smax = step_variance
    
    for _ in range(max_iterations):
        diff = target - current
        
        if abs(diff) <= .25:
            break
        
        step = diff * rng.uniform(smin, smax) * x
        current += step
        
        history.append(current)
    return history


def clamp[T: (int, float)](value: T, lo: T, hi: T) -> T:
    return max(lo, min(value, hi))
