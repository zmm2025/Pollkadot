"""Douglas-Peucker on topology arcs (endpoints kept => shared borders stay shared).
usage: simplify.py in.pkl out.pkl tol"""
import pickle, sys
import numpy as np

def dp_mask(P, tol):
    n = len(P); keep = np.zeros(n, bool); keep[0] = keep[-1] = True
    if n <= 2: return keep
    closed = np.allclose(P[0], P[-1])
    stack = []
    if closed:
        # split closed ring at farthest point from start
        d = np.hypot(*(P - P[0]).T); m = int(np.argmax(d)); keep[m] = True
        stack = [(0, m), (m, n-1)]
    else:
        stack = [(0, n-1)]
    while stack:
        a, b = stack.pop()
        if b - a < 2: continue
        A, B = P[a], P[b]; seg = P[a+1:b]
        dx, dy = B - A; L = np.hypot(dx, dy)
        if L == 0: d = np.hypot(*(seg - A).T)
        else: d = np.abs(dx*(seg[:, 1]-A[1]) - dy*(seg[:, 0]-A[0]))/L
        i = int(np.argmax(d))
        if d[i] > tol:
            m = a+1+i; keep[m] = True; stack += [(a, m), (m, b)]
    return keep

if __name__ == '__main__':
    T = pickle.load(open(sys.argv[1], 'rb')); tol = float(sys.argv[3])
    T['arcs'] = [a[dp_mask(a, tol)] for a in T['arcs']]
    # closed arcs must keep >=4 points (3 distinct) to remain a polygon
    print('points after', sum(len(a) for a in T['arcs']))
    pickle.dump(T, open(sys.argv[2], 'wb'))
