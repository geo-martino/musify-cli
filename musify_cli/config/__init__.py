"""
Stores all config objects for configurable operations.

A config object stores the arguments with which to either call a specific method
or to instantiate an object related to those arguments.

The crucial principle is that the config arguments should not need to be used directly to call methods
or instantiate objects. This should all be handled within the same config object to ensure modifications
in the interface of dependent objects or extensions of functionality in any way can be easily adapted to
through functional proximity in logic.
"""
