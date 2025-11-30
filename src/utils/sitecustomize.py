# Auto-loaded by Python if present on sys.path.
# Writes /tmp/ultra_cm.txt every time Ultrasonic.get_distance() is called.
try:
    from pathlib import Path
    import ultrasonic as _ultra
    _orig_get = _ultra.Ultrasonic.get_distance
    def _get_with_cache(self, *a, **kw):
        d = _orig_get(self, *a, **kw)
        try:
            if d is not None:
                Path('/tmp/ultra_cm.txt').write_text(f"{float(d):.1f}")
        except Exception:
            pass
        return d
    _ultra.Ultrasonic.get_distance = _get_with_cache
    # Optional: mark that the patch is active
    _patched = True
except Exception:
    # If ultrasonic module isn’t importable in this process, do nothing.
    pass
