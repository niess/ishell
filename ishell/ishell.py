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

import getopt
import os
import sys
from . import IShell


def main():
    # Parse the options
    opts, args = getopt.getopt(sys.argv[1:], "c:")


    # Process the arguments
    if opts or args:
        # Interpreted mode
        ish = IShell()
        ish.initialise()

        class ExitGracefully(Exception):
            pass

        try:
            for _, cmd in opts:
                if ish.onecmd(cmd):
                    raise ExitGracefully()

            for path in args:
                with open(path, "rb") as f:
                    for line in f:
                        if ish.onecmd(line):
                            raise ExitGracefully()
        finally:
            ish.finalise()

    else:
        # Interactive mode
        IShell().cmdloop()


if __name__ == "__main__":
    main()
