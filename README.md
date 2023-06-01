# Dbsamizdapper

The "blissfully naive PostgreSQL database object manager"
This is based on the original `dbsamizdat` code from https://git.sr.ht/~nullenenenen/DBSamizdat/ a version of which was previously hosted at `https://github.com/catalpainternational/dbsamizdat`

Full disclosure: That one (https://git.sr.ht/~nullenenenen/DBSamizdat/ which is also on pypi) is definitely less likely to have bugs, it was written by a better coder than I am, the original author is "nullenenenen <nullenenenen@gavagai.eu>"

## New features

This fork is based on a rewrite which I did to better understand the internals of `dbsamizdat` as we use it in a few different projects. The changes include:

 - A target pyver of about ~3.10
 - Type hints throughout the codebase
 - Changed from `ABC` to `Protocol` type for inheritance
 - Poetry for dependency and build management
 - Compat with both `psycopg` and `psycopg3`
 - Opinionated code formatting
   - black + isort
   - replaced `lambda`s
 - some simple `pytest` functions

and probably many more undocumented changes

## Original README

Check out the original readme for rationale and how-to documentation
