#!/usr/bin/env python
# -*- coding: utf-8 -*-


from functools import wraps, lru_cache


def disable(func):
    '''
    Disable a decorator by re-assigning the decorator's name
    to this function. For example, to turn off memoization:
    >>> memo = disable
    '''

    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    return wrapper


def decorator(func):
    '''
    Decorate a decorator so that it inherits the docstrings
    and stuff from the function it's decorating.
    '''

    @wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    return wrapper


def countcalls(func):
    '''Decorator that counts calls made to the function decorated.'''

    @wraps(func)
    def wrapper(*args, **kwargs):

        wrapper.calls += 1

        return func(*args, **kwargs)

    wrapper.calls = 0

    return wrapper


def memo(func):
    '''
    Memoize a function so that it caches all return values for
    faster future lookups.
    '''

    @wraps(func)
    def wrapper(*args, **kwargs):

        cache_key = args + tuple(kwargs.items())

        if cache_key not in wrapper.cache:

            wrapper.cache[cache_key] = func(*args, **kwargs)

        return wrapper.cache[cache_key]

    wrapper.cache = dict()

    return wrapper


def n_ary(func):
    '''
    Given binary function f(x, y), return an n_ary function such
    that f(x, y, z) = f(x, f(y,z)), etc. Also allow f(x) = x.
    '''

    @wraps(func)
    def wrapper(*args, **kwargs):

        if len(args) == 1:
            if func.__name__ == "foo":
                second = 0
            else:
                second = 1
            return func(args[0], second)

        return func(args[0], wrapper(*args[1:]), **kwargs)

    return wrapper


def trace(shift_arg):

    '''Trace calls made to function decorated.

    @trace("____")
    def fib(n):
        ....

    >>> fib(3)
     --> fib(3)
    ____ --> fib(2)
    ________ --> fib(1)
    ________ <-- fib(1) == 1
    ________ --> fib(0)
    ________ <-- fib(0) == 1
    ____ <-- fib(2) == 2
    ____ --> fib(1)
    ____ <-- fib(1) == 1
     <-- fib(3) == 3

    '''

    def real_decorator(func):

        @wraps(func)
        def wrapper(*args, **kwargs):

            wrapper.depth += 1

            print("{} --> {}({})".format(shift_arg * wrapper.depth, func.__name__, args[0]))  # конечно лучше оставить args, это для эстэтики

            res = func(*args, **kwargs)

            print("{} <-- {}({}) == {}".format(shift_arg * wrapper.depth, func.__name__, args[0], res))  # конечно лучше оставить args, это для эстэтики

            wrapper.depth -= 1

            return res

        wrapper.depth = -1

        return wrapper

    return real_decorator


# memo = disable


@countcalls
@memo
@n_ary
def foo(a, b):
    return a + b


@countcalls
@memo
@n_ary
def bar(a, b):
    return a * b


@countcalls
@trace("####")
@memo             #можно использовать lru_cache без написания доп декоратора @memo
def fib(n):
    '''Some doc'''

    return 1 if n <= 1 else fib(n-1) + fib(n-2)


def main():

    print(foo(4, 3))
    print(foo(4, 3, 2))
    print(foo(4, 3))
    print("foo was called", foo.calls, "times")

    print(bar(4, 3))
    print(bar(4, 3, 2))
    print(bar(4, 3, 2, 1))
    print("bar was called", bar.calls, "times")

    print(fib.__doc__)
    fib(3)
    print(fib.calls, 'calls made')


if __name__ == '__main__':
    main()
