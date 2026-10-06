"""A capacity-expansion planner on specsolve: a solve job, an archive directory, and a site that reads it.

The solve job (:mod:`showcase.solve`) is the only module that imports specsolve.
The queries (:mod:`showcase.warehouse`) and the site's data loader read the
parquet the job archived, and nothing else.
"""
