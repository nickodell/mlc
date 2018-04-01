# MarioLANG Compiler

MarioLANG Compiler (mlc) will compile programs from MarioLANG into C.

# Usage

    $ ./mlc.py <program name>
    $ gcc ml.c
    $ ./a.out

# Internals

mlc walks the MarioLANG program and constructs a finite state machine, performs some optimizations to reduce the size of the graph, then turns that graph into a C program.

# Known problems

* Input is line-buffered, unlike many mariolang implementations.
* Memory is statically allocated, and no over/underflow checks are made.

# Questions?

Contact the author at nickodell@gmail.com
