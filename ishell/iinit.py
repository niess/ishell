#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  Copyright (C) 2017 Université Clermont Auvergne, CNRS/IN2P3, LPC
#  Author: Valentin NIESS (niess@in2p3.fr)
#
#  Irods in a nutSHELL (ISHELL).
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU Lesser General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU Lesser General Public License for more details.
#
#  You should have received a copy of the GNU Lesser General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>

import getpass
import os
import stat
import sys
from irods.password_obfuscation import encode


def main():
    # Read the password from the command line
    try:
        password = getpass.getpass("Enter irods password:")
        confirm = getpass.getpass("Confirm password:")
    except KeyboardInterrupt:
        print("^C")
        sys.exit(0)
    except EOFError:
        print("^D")
        sys.exit(0)
    if password != confirm:
        raise ValueError("confirmation does not match")


    # Encode and dump the password
    path = os.path.expanduser("~/.irods")
    if not os.path.exists(path):
        os.makedirs(path)

    path = os.path.join(path, ".irodsA")
    uid = os.getuid()
    with open(path, "wb+") as f:
        f.write(encode(password))
    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    print("Irods password has been set")


if __name__ == "__main__":
    main()
