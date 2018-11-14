# ISHELL
( **I**rods in a nut**SHELL** )


## Description

[ISHELL][ISHELL] is a UNIX shell like client for
[iRODS](https://github.com/irods/irods).  It is written in pure Python,
encapsulating the [python-irodsclient][client]. It provides similar
functionalities than the
[irods-icommands](https://github.com/irods/irods_client_icommands) package but
following a different strategy. Instead of prefixing UNIX like commands ISHELL
simulates an ssh connection to an iRODS server. From there, the usual UNIX
syntax can be used, e.g. `cd`, `ls`, `mkdir`, `rm`, ...

**Note** that the current version is very preliminary.


## Installation

From [PyPi](https://pypi.org/project/irods-shell), e.g. using `pip`:
```bash
pip install --user irods-shell

```
Alternatively, you can also clone the [source](https://github.com/niess/ishell)
and run `python setup.py install --user`. Note that you'll need
[python-irodsclient][client] to be installed first.


## Documentation

The ISHELL package currently exports two executables: `iinit` and `ìshell`.
You might need to add their install location to your `PATH`.

* The `iinit` executable is provided as a partial replacement to the standard
  one, from irods-icommands. It allows to encode your iRODS password in order
  to authenticate. You'll also need to configure your `irods_environment.json`
  file. Note that currently this is the only supported mode of authentication.

* The `ishell` executable simulates an ssh connection to your iRODS server.
  Once connected you can type `help` for a list of the supported commands.
  Alternatively it can also be run in interpreted mode, e.g.
  `ìshell -c "cd ..; ls"` or reading from a script file, e.g.
  `ìshell script.ish`.


## License

The [ISHELL][ISHELL] package is under the **GNU LGPLv3** license. See the
provided [LICENSE][LICENSE] and [COPYING.LESSER][COPYING] files.


[client]: https://github.com/irods/python-irodsclient
[ISHELL]: https://github.com/niess/ishell
[LICENSE]: https://github.com/niess/ishell/blob/master/LICENSE
[COPYING]: https://github.com/niess/ishell/blob/master/COPYING.LESSER
