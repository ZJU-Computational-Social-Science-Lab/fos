# Package marker for the integration tests. This keeps pytest from
# importing this folder's fixtures under the bare module name "conftest",
# which would shadow the parent twin2k10r suite's fixtures when both
# folders are collected in one run.
