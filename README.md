# CFFI Generator

This module will read in the output produced by GCC, and parse it to easy-to-use json-formatted headers.

Calling a C shared library from a dynamic language shouldn't mean that you'll spend a week writing bindings. It's boring and stupid.

With the help of this module you'll get something the damn operating system should have provided you in the first place - the machine readable instructions for calling your favorite shared libraries.

Some of the resulting bindings may be broken, or the target language cannot support everything. It's common to not support varargs for example. Be sure to read entries from the table on-demand, or just ignore the entries that break your FFI. 

There are some example scripts and their outputs dropped into the repository, if you like to look on what it produces and how.

It's Slightly Incomplete.

## Install

Install [lrkit](https://github.com/cheery/lrkit).

## Usage

The following command fills up an environment from the header files:

    import parser
    env = parser.default_env()
    parser.parse(env, [
        '/usr/include/SDL2/SDL.h'
    ])

Every time the parser runs, it generates the LR(1) tables to run the parser. This takes a second or two, even if you were using pypy.

This operation may crash on SnError. If that happens, do not attempt to rewrite the headers because that defeats the point of this tool. Instead file an issue at [lrkit/issues](https://github.com/cheery/lrkit/issues), so we can adjust the tool to match the input.

The parser doesn't do much to understand the data. The names, types and structures appear in the dump just like they appear in the input file. The second step is to translate the output into a nice json dump, which is compatible with most languages that do not have two separate type namespaces in them as a convenience.

For this we've got a Translator. It's a bit like a template for your program:

    from translator import Translator
    def rename_type(name):
        return re.sub(r"^SDL_", r"", name)

    translate = Translator(env, rename_type)
    translate.blacklist.update([
        '_IO_marker',
        '_IO_FILE',
    ])
    translate.bluelist.update({
        'SDL_AudioCVT': 'AudioCVT',
        'SDL_assert_data': 'assert_data',
        'SDL_PixelFormat': 'PixelFormat',
        'SDL_RWops': 'RWops',
    })

The translator renames constructs in the environment, after your command. You can pass it the constructs you want to include in your .json output. Here's an example how to etract and rename some C functions with a regex:

    functions = {}
    variables = {}

    for name in env.names:
        if re.match(r'^SDL_\w', name):
            typespec = translate.declarator(env.names[name])
            name = re.sub(r"^SDL_", r"", name)
            if is_function(typespec):
                functions[name] = typespec
            else:
                variables[name] = typespec

You probably want some constants with those functions. The parser parses also the macroenvironment dumped by GCC, you can obtain it from the environment, as long as you look after unresolved entries:

    constants = {}
    for name, value in env.constants.iteritems():
        if re.match(r'^SDL_\w', name):
            if isinstance(value, (int, str)):
                name = re.sub(r"^SDL_", r"", name)
                constants[name] = value

The translate.types will contain the types required by the commands you requested. Finally just print it out!

    print json.dumps({
        'constants': constants,
        'functions': functions,
        'types': translate.types,
        'variables': variables}, indent=2, sort_keys=True)
