import functools


def benchmark(do_benchmark=True):
    """
    Decorator to mark a function for benchmarking or no benchmarking.
    """

    def wrap(fxn):
        def marcabanca_wrapper(*args, **kwargs):
            return fxn(*args, **kwargs)

        # Hacky. Better solution is to return a callable object,
        # but pytest does not seem to bind those correctly.
        marcabanca_wrapper._marcabanca = {'benchmark': do_benchmark}

        return marcabanca_wrapper

    return wrap
