#!/bin/bash

# Root directory
ishell_dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Set the PATH for binaries
bin_dir=$ishell_dir/bin
[[ "$PATH" =~ "${bin_dir}" ]] || export PATH=${bin_dir}:$PATH
