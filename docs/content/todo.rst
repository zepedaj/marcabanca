To-do's
=======

Next features
---------------
* When choosing a non-exact model, attempt to choose one from the first machine first, and then attempt to minimize the python env difference. Display what differences there are. This should mitigate the situation where a new python module was installed or an existing one was upgraded.
  * Give the option to specify the reference machine/environment pair programatically.
    * CLI tool to analyze / modify contents of JSON files, including:
      * Number of referenes per test.
      * Difference between environment configurations.
      * Configuration of current environment.
      * Ability to cleanup from the references (or rename) orphan time references (e.g., following a code refactoring).
  * Raise exception when timing test does not pass.
  * Do statistical analysis to ensure errors are raised only in statistically significant situations.
  * Make it possible to run tests/reference construction in parallel as much as possible.
  * Save references as soon as they are built.
* When creating references, add message at end of report indicating the number of new references created, and the total number of tests to run.
* Save the last report in a temporary file and allow viewing, re-sorting and copying of this last report. Fail gracefully without breaking the test run if unable to create the temporary file.
* Display in color coded columns whether the same machine and python env are being compared against, as well as the machine / python env config.



Project-wide to-do's
---------------------
