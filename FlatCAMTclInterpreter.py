############################################################
# FlatCAM: 2D Post-processing for Manufacturing            #
# http://flatcam.org                                       #
# MIT Licence                                              #
############################################################

"""
Pure-Python command interpreter used as a drop-in replacement for the Tcl
interpreter (``tkinter.Tcl()``) that historically powered the FlatCAM shell.

Only the subset of the Tcl API actually used by FlatCAM is implemented:

    * ``createcommand(name, fcn)`` - register a callable under ``name``.
    * ``eval(text)`` - tokenize and execute one or more commands and return the
      result of the last command as a string.

This removes the dependency on native Tcl/Tk, which is not available in the
default Flatpak runtimes.

Supported syntax:
    * Multiple commands separated by newlines or ``;``.
    * Comments starting with ``#`` where a command name is expected.
    * Word grouping with double quotes ``"..."`` (with ``$var`` substitution)
      and braces ``{...}`` (literal, nestable).
    * Backslash escaping.
    * Minimal ``set <name> <value>`` / ``$var`` substitution and ``puts``.

Not supported (documented limitation): command substitution ``[...]``, control
flow (``if``/``for``/``foreach``), ``expr`` and user defined procs.
"""


class TclInterpreterError(Exception):
    """Raised when command parsing or execution fails."""
    pass


class TclCommandInterpreter(object):
    """
    Minimal command dispatcher mimicking the ``tkinter.Tcl()`` interface used by
    FlatCAM (``createcommand`` and ``eval``).
    """

    def __init__(self, error_class=None):
        # Registered commands: name -> callable(*args) -> str|None
        self._commands = {}
        # Interpreter variables (for the minimal ``set`` / ``$var`` support)
        self._variables = {}
        # Exception type raised on errors (defaults to TclInterpreterError so
        # the module works stand-alone; FlatCAM passes App.TclErrorException).
        self._error_class = error_class or TclInterpreterError

    # -- Public API compatible with tkinter.Tcl() ------------------------------

    def createcommand(self, name, fcn):
        """Register ``fcn`` so it can be invoked as ``name`` from the shell."""
        self._commands[name] = fcn

    def eval(self, text):
        """
        Execute one or more commands contained in ``text`` and return the
        result of the last command as a string.
        """
        commands = self._split_commands(text)

        result = None
        for words in commands:
            if not words:
                continue
            result = self._dispatch(words)

        # Preserve the historical behaviour where a Python ``None`` result was
        # turned into the string 'None' by the Tcl bridge; FlatCAMApp relies on
        # comparing the result against the literal 'None'.
        if result is None:
            return 'None'
        return str(result)

    # -- Dispatch --------------------------------------------------------------

    def _dispatch(self, words):
        name = words[0]
        args = words[1:]

        if name == 'set':
            return self._cmd_set(args)
        if name == 'puts':
            return self._cmd_puts(args)

        if name not in self._commands:
            raise self._error_class('invalid command name "%s"' % name)

        return self._commands[name](*args)

    def _cmd_set(self, args):
        if len(args) == 1:
            varname = args[0]
            if varname not in self._variables:
                raise self._error_class('can\'t read "%s": no such variable' % varname)
            return self._variables[varname]
        if len(args) == 2:
            self._variables[args[0]] = args[1]
            return args[1]
        raise self._error_class('wrong # args: should be "set varName ?newValue?"')

    def _cmd_puts(self, args):
        # Mirrors the previous Tcl override: a single argument is returned
        # (captured by the shell) instead of being printed to stdout.
        if len(args) == 1:
            return args[0]
        # Support the ``puts -nonewline`` form and multi-arg by printing.
        text = args[-1] if args else ''
        print(text)
        return ''

    # -- Parsing ---------------------------------------------------------------

    def _split_commands(self, text):
        """
        Split ``text`` into a list of commands, each being a list of word
        tokens. Commands are separated by newlines or ``;``. Comments (``#``)
        are honoured only where a command name is expected.
        """
        commands = []
        words = []
        current = None          # current word buffer (None => between words)
        i = 0
        n = len(text)
        in_comment = False

        def flush_word():
            nonlocal current
            if current is not None:
                words.append(self._substitute(current))
                current = None

        def flush_command():
            nonlocal words
            flush_word()
            if words:
                commands.append(words)
                words = []

        while i < n:
            ch = text[i]

            if in_comment:
                if ch == '\n':
                    in_comment = False
                i += 1
                continue

            # Command separators.
            if ch == '\n' or ch == ';':
                flush_command()
                i += 1
                continue

            # Whitespace between words.
            if ch in (' ', '\t', '\r'):
                flush_word()
                i += 1
                continue

            # Comment start: only when we are at the beginning of a command.
            if ch == '#' and current is None and not words:
                in_comment = True
                i += 1
                continue

            # Brace-quoted word (literal, nestable, no substitution).
            if ch == '{' and current is None:
                token, i = self._read_braces(text, i)
                words.append(token)  # no substitution inside braces
                current = None
                continue

            # Double-quoted word (with substitution).
            if ch == '"' and current is None:
                token, i = self._read_quotes(text, i)
                words.append(self._substitute(token))
                current = None
                continue

            # Backslash escape.
            if ch == '\\' and i + 1 < n:
                if current is None:
                    current = ''
                current += text[i + 1]
                i += 2
                continue

            # Regular character.
            if current is None:
                current = ''
            current += ch
            i += 1

        flush_command()
        return commands

    def _read_braces(self, text, i):
        """Read a ``{...}`` group starting at index ``i`` (the opening brace)."""
        n = len(text)
        depth = 0
        i += 1  # skip opening brace
        start = i
        buf = []
        while i < n:
            ch = text[i]
            if ch == '\\' and i + 1 < n:
                buf.append(text[i + 1])
                i += 2
                continue
            if ch == '{':
                depth += 1
                buf.append(ch)
                i += 1
                continue
            if ch == '}':
                if depth == 0:
                    return ''.join(buf), i + 1
                depth -= 1
                buf.append(ch)
                i += 1
                continue
            buf.append(ch)
            i += 1
        raise self._error_class('missing close-brace')

    def _read_quotes(self, text, i):
        """Read a ``"..."`` group starting at index ``i`` (the opening quote)."""
        n = len(text)
        i += 1  # skip opening quote
        buf = []
        while i < n:
            ch = text[i]
            if ch == '\\' and i + 1 < n:
                buf.append(text[i + 1])
                i += 2
                continue
            if ch == '"':
                return ''.join(buf), i + 1
            buf.append(ch)
            i += 1
        raise self._error_class('missing "')

    def _substitute(self, token):
        """
        Perform minimal ``$var`` substitution on ``token``. Names are made of
        alphanumeric characters and underscores. ``$`` not followed by a valid
        name is left untouched.
        """
        if '$' not in token:
            return token

        result = []
        i = 0
        n = len(token)
        while i < n:
            ch = token[i]
            if ch == '$' and i + 1 < n and (token[i + 1].isalpha() or token[i + 1] == '_'):
                j = i + 1
                while j < n and (token[j].isalnum() or token[j] == '_'):
                    j += 1
                name = token[i + 1:j]
                if name in self._variables:
                    result.append(str(self._variables[name]))
                else:
                    raise self._error_class('can\'t read "%s": no such variable' % name)
                i = j
                continue
            result.append(ch)
            i += 1
        return ''.join(result)
