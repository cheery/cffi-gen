import parser

primitive_types = {
    'void':               "void",
    'char':               "ubyte",
    'unsigned char':      "ubyte",
    'signed char':        "sbyte",
    'short':              "short",
    'unsigned short':     "ushort",
    'int':                "int",
    'unsigned int':       "uint",
    'signed int':         "int",
    'long':               "long",
    'unsigned long':      "ulong",
    'long long':          "llong",
    'unsigned long long': "ullong",
    'float':              "float",
    'double':             "double",
    'long double':        "ldouble",
}

gcc_primitive_types = {
    '__QI__': "i8",
    '__HI__': "i16",
    '__SI__': "i32",
    '__DI__': "i64",
    '__SF__': "float",
    '__DF__': "double",
}

class Translator(object):
    def __init__(self, env, rename_type):
        self.env = env
        self.rename_type = rename_type
        self.alias = {} # Maps c names to translated names.
        self.renamings = {} # umm...
        self.types = {}
        self.shadow_types = {}
        self.translated = set()
        self.blacklist = set() # Blacklist turns structs opaque
        self.bluelist = {} # Bluelist renames structs/unions

    def declarator(self, declarator):
        if declarator is Ellipsis:
            raise Exception("vararg")
        # C declarators have a specifier, with modifiers
        # stacked on top. We go through the stack and
        # produce the typespec.
        typespec = self.specifiers(declarator)
        return self.declarator_chain(declarator, typespec)

    def declarator_chain(self, declarator, typespec):
        for which, params in reversed(declarator):
            if which == 'function':
                argtypes = [self.declarator(param) for param in params if param != Ellipsis]
                if argtypes == ['void']:
                    argtypes = []
                typespec = {"type": "cfunc",
                    "argtypes": argtypes,
                    "restype": typespec,
                    "vararg": Ellipsis in params}
            elif which == 'pointer':
                # ignoring specifiers of a pointer
                if isinstance(typespec, str):
                    typespec += '*'
                else:
                    typespec = {"type": "pointer", "to": typespec}
            elif which == 'array':
                typespec = {"type": "array", "ctype": typespec, "length": params}
            else:
                # If this happens, just fill up the missing specs and the results
                # they should translate to.
                raise Exception("Translator for declarator not implemented: %r" % declarator)
        return typespec

    def specifiers(self, declarator):
        ctype = primitive_type(declarator)
        if ctype is not None:
            return ctype
        if len(declarator.specifiers) == 1:
            typename = declarator.specifiers[0]
            if is_structure_union(declarator):
                if declarator is None:
                    assert False # hmm...
                return self.typedecl(declarator)
            elif isinstance(typename, parser.Enum):
                return self.declarator_chain(declarator, 'int')
            elif isinstance(typename, str):
                typedecl = self.env.types[typename]
                if typedecl in self.alias:
                    return self.alias[typedecl]
                aliased = unroll_typedef(self.env, typedecl)
                if isinstance(aliased, str):
                    self.alias[typedecl] = aliased
                    return aliased
                else:
                    if self.visit(typename):
                        if typedecl is None:
                            assert False, typename # hmm...
                        name = self.rename(typename)
                        ctype = self.typedecl(typedecl)
                        if ctype == name: # For the interesting case of:
                            return name   # typedef struct name name;
                        assert name not in self.types, name
                        self.types[name] = ctype
                        return name
                    return self.rename(typename)
        raise Exception("Translator for specifier not implemented: %r" % declarator.specifiers)

    def typedecl(self, typedecl):
        if typedecl is None:
            assert False # hmm...
        if is_structure_union(typedecl):
            typespec = typedecl.specifiers[0]
            if typespec.name in self.bluelist and not self.visit(typespec):
                res = self.bluelist[typespec.name]
            elif typespec.fields is None or typespec.name in self.blacklist:
                res = {'type': 'opaque'}
            else:
                fields = []
                res = {'type': typespec.which, 'fields': fields}
                if typespec.name is not None:
                    assert typespec.name not in self.shadow_types, typespec.name
                    # At this point, you may add the type to blacklisted list.
                    # ...Or into bluelist, if you want it in anyway.
                    self.shadow_types[typespec.name] = res
                if typespec.name in self.bluelist:
                    name = self.bluelist[typespec.name]
                    assert name not in self.types, name
                    self.types[name] = res
                    res = name
                for field in typespec.fields:
                    fields.append([field.name, self.declarator(field)])
        else:
            res = self.specifiers(typedecl)
        return self.declarator_chain(typedecl, res)

    def rename(self, name):
        renamed = self.rename_type(name)
        self.renamings[name] = renamed
        return renamed

    def visit(self, obj):
        if obj in self.translated:
            return False
        self.translated.add(obj)
        return True

def is_structure_union(typedecl):
    if len(typedecl.specifiers) == 1:
        return isinstance(typedecl.specifiers[0], (parser.Structure, parser.Union))

# This thing tries to 'unroll' the typedef into a string.
def unroll_typedef(env, declarator):
    if isinstance(declarator, str) or declarator is None:
        return declarator
    ctype = primitive_type(declarator)
    if ctype is None:
        if len(declarator.specifiers) == 1:
            basetype = declarator.specifiers[0]
            if isinstance(basetype, str):
                ctype = unroll_typedef(env, env.types[basetype])
            if isinstance(basetype, parser.Enum):
                ctype = 'int'
    if ctype is None:
        return
    for which, params in declarator.attributes:
        if which == 'attribute':
            for cell in params:
                if isinstance(cell, list) and cell[0] == '__mode__':
                    assert ctype in ('int', 'uint'), ctype
                    ctype = gcc_primitive_types[cell[1]]
                    continue
                raise Exception("unknown attribute param: %r" % (cell,))
            continue
        if len(declarator.attributes) > 0:
            raise Exception("unknown attribute: %r in %r" % (declarator.attributes, declarator))
    for which, params in reversed(declarator):
        if which == 'pointer':
            ctype += '*'
        else:
            return
    return ctype

def primitive_type(declarator):
    if all(isinstance(a, str) for a in declarator.specifiers):
        string = ' '.join(declarator.specifiers)
        if string in primitive_types:
            return primitive_types[string]
        elif len(declarator.specifiers) > 0 and declarator.specifiers[-1] == 'int':
            string = ' '.join(declarator.specifiers[:-1])
            if string in primitive_types:
                return primitive_types[string]

def is_function(typespec):
    return isinstance(typespec, dict) and typespec['type'] == 'cfunc'
