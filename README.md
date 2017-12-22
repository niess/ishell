# ISHELL
( **I**rods in a nut**SHELL** )

## Description

ISHELL is a UNIX shell like client for [iRODS](https://github.com/irods/irods).
It is written in pure Python, encapsulating the
[python-irodsclient](https://github.com/irods/python-irodsclient). It provides
similar functionalities than the
[irods-icommands](https://github.com/irods/irods_client_icommands) package
but following a different strategy. Instead of prefixing UNIX like commands
ISHELL simulates an ssh connection to an iRODS server. From there, the usual
UNIX syntax can be used, e.g. `cd`, `ls`, `mkdir`, `rm`, ...

**Note** that the current version is very preliminary.


## Installation

Clone the present repository with its dependencies and then run the
[Makefile](Makefile), e.g:

```bash
git clone --recursive https://github.com/niess/ishell
cd ishell
make
```


## Documentation

The ISHELL package currently exports two executables: `iinit` and `ìshell`.
You might source the provided [setup.sh](setup.sh) file in order to add them
to your path.

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

The ISHELL package is under the **GNU LGPLv3** license. See the provided
[LICENSE](LICENSE) and [COPYING.LESSER](COPYING.LESSER) files.
