"""Bounded rotating selections without changing persisted submission evidence."""

def submission_batch(items, *, limit=100, offset=0):
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("Submission batch limit is invalid")
    if type(offset) is not int or offset < 0:
        raise ValueError("Submission batch offset is invalid")
    rows = tuple(items)
    if not rows:
        return ()
    start = offset % len(rows)
    return (rows[start:] + rows[:start])[:limit]
