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

# Other

Questions? Contact the author at nickodell@gmail.com.

mlc is inspired by a [blog post](https://blind.guru/MarioLANG.html) written by Mario Lang. This implementation is based upon an interpreter written by [mynery](https://github.com/mynery/mariolang.rb).
