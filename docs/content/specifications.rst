Specifications
===============

Stores N (defaults to 10) run-times indexed by test id (e.g., 'my.module::MyClass::my_function'), machine hardware configuration and python environment configuration (collectively the environment). A gamma distribution is fit to these runtimes and further stored along with the runtimes.

All these configurations (machine and python environment configurations, runtimes) are stored as JSON files. By default, these files are stored in the root test folder under a 'marcabanca' subfolder. These JSON files are meant to be stored in the github repository together with the tests' source code.

Upon testing, each test's runtime is compared to the gamma distribution for the current environment, and a percentile threshold is applied to determine whether the test passes or fails.

By default, all tests compared against their original runtime to detect runtime regressions automatically. Upon running these tests the first time, the reference runtimes are stored in the configuration files.

For repeatability, one should ensure the exact same environment is used. Marcabanca tries to find the exact configuration. If it is not found, it will find the closest configuration and compare to that configuration.

Test functions and methods can be explicitly marked as benchmark functions by decorating them with  :func:`marcabanca.benchmark(True)` (``True`` is the default and can be ommitted) or explicitly excluded from bencharmking using :func:`marcabanca.benchmark(False)`.

Tests that are slower than a few tens of milli seconds will not be repeatable and should be excluded (e.g., by decorating them with :func:`marcabanca.benchmark(False)`)
