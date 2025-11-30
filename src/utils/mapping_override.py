def remap2(l, r):
    # invert forward/back
    l, r = -l, -r
    # swap left/right
    return r, l

def remap4(lf, lr, rf, rr):
    # invert forward/back
    lf, lr, rf, rr = -lf, -lr, -rf, -rr
    # swap left/right pairs
    return rf, rr, lf, lr
