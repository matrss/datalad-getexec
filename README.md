# DataLad extension for code execution in get commands

[![check](https://github.com/matrss/datalad-getexec/actions/workflows/check.yml/badge.svg)](https://github.com/matrss/datalad-getexec/actions/workflows/check.yml)
[![codecov](https://codecov.io/gh/matrss/datalad-getexec/branch/main/graph/badge.svg?token=W8PMJRM66H)](https://codecov.io/gh/matrss/datalad-getexec)
[![docs](https://readthedocs.org/projects/datalad-getexec/badge/?version=latest)](https://datalad-getexec.readthedocs.io/en/latest/?badge=latest)

CAUTION: Work-in-Progress!

This DataLad extension provides facilities to register arbitrary commands for files in git-annex,
which are then executed if `datalad get` is called on those files (and they are not yet present).

## How do I use this?

This extension provides a new high-level datalad command called `getexec`
which can be used to register commands on files.

In the following we will assume that we have the extension installed
and are inside a DataLad dataset.

As a simple example,
we can register a command that writes "Hello World!" into a text file called "test.txt":
```
datalad getexec --path test.txt -- 'bash' '-c' 'printf "Hello World!" > "$1"' 'test-cmd'
```
As a result of this,
we now have the file "test.txt" with it's expected content.
Since we told git-annex that we can recreate this file with the specified bash call,
we can now safely drop the file
and then automatically get it recreated:
```
datalad drop test.txt
datalad get test.txt
```

Since our registered program might depend on some other annex'ed files
we can specify those dependencies as well:
```
datalad getexec --path depends-on-test.txt -i test.txt -- 'bash' '-c' '(cat test.txt; printf "\nMore Text.") > "$1"' 'test-cmd'
```
This way,
if `datalad get` is called on "depends-on-test.txt" git-annex will make sure,
that "test.txt" is present before executing the registered command.
Therefore,
the following will work:
```
datalad drop test.txt
datalad drop depends-on-test.txt
datalad get depends-on-test.txt
```

There are some limitations to what commands can be registered.
First of all,
there is no shell interpretation happening;
the command is essentially passed verbatim to python's `subprocess.run`.
This is why the examples above look a bit more complex with the call to bash.
In the above examples,
each quoted part after `--` becomes one element in the list passed to `subprocess.run`.
In practice,
it would be a good idea to externalize the command into e.g. a shell script
and have a single argument in the `getexec` call.

Second,
the command is expected to always produce a single output file,
the location of which is passed as the first (and only) argument to the command.
This is the `$1` in the bash calls above.

Lastly,
since the command is executed in the context of a `get`,
the resulting file is always expected to remain the same.
This means that two consecutive calls to the command need to produce files with identical checksums,
otherwise git-annex will complain.
Essentially,
the command is expected to behave somewhat like a pure function.
If this does not fit your use-case you are probably looking for DataLad's builtin `run` and `rerun`.

## How does it work?

This extension works by implementing a new git-annex special remote which kind of abuses the URL handling of git-annex.
The special remote takes responsibility of all URLs with a scheme of "getexec:";
encoded inside of these URLs then is the necessary information to re-execute the registered command.
The DataLad part of the extension simply takes the user input,
generates a matching URL for it
and then registers the URL with git-annex.

When `get`ing a file that is not currently present,
git-annex will do it's usual thing to determine from where to fetch the data.
If git-annex determines that the special remote of this extension should provide the data
then it will rerun the registered command.
