Pitfalls
==========
* Statefull tests are not supported. Marcabanca calls tests multiple times internally both at reference-creation time and at test time. It is assumed the times measured for the different calls are comparable (i.e., stationary variables).
  * One source of non-stationarity is module loading overhead. Marcabanca avoids this by ignoring the first call to a module. This means that test time collection requires at least two calls to each test function (one plus the number of test runs specified with CLI argument ``--mb-num-test-runs``). The same is true for reference time collection.
